// Live screen (live.html): the trainer's WebRTC connection to the live
// process, set up by itself when the page opens.
//
// 1. The microphone, once, with the browser's voice processing off (echo
//    cancellation, noise suppression and gain control would change the
//    voice that gets measured). Blocked: it says so and stops.
// 2. GET data-connect-url (web:session_connect): the live process's offer
//    (an audio transceiver it only receives on, and a "control" data
//    channel) with the ICE servers to use.
// 3. A peer connection with those, the offer in, the mic's track on the
//    offer's audio transceiver, the answer made. The live process doesn't
//    take ICE candidates one by one (no trickle ICE), so the answer is only
//    sent once the browser has gathered them all (or after GATHER_MS).
// 4. POST the answer to the same URL. The connection then comes up by
//    itself; the "control" channel arrives as a datachannel event.
//
// The screen: the loading screen ([data-live-loading], its status line saying
// connecting, reconnecting or a stop) until the connection is up the first
// time; then the session content ([data-live-content], session.js), fetched
// fresh with content.session.refresh(), and the loading screen only shows
// again, as a slim bar above it, while the connection is down.
//
// The content has two views, as the session's JSON says: while a talk is
// recording or paused, the talk view (talk_content.html) under the talk
// header (talk_header.html: "Talk n", Recording or Paused, its clock); else
// the session view (session_content.html) under the session header. After
// every change (a talk started, paused, resumed or ended) the JSON is
// fetched again (refresh), and the screen follows it.
//
// The buttons: Start talk (the session header's and the talks card's),
// Pause / Resume send start_talk, pause_talk, resume_talk on the "control"
// channel; End talk is POST the talk's finish_url (web:talk_finish). Finish
// session is the confirm dialog's (confirm-dialog.js). A refusal (a talk is
// already going, the connection isn't up) shows in [data-live-message].
// Commands go as {"id": n, "type": ...}; the reply has the same id.
//
// The browser's own recording of each talk: a MediaRecorder on the mic,
// started when the live process says the talk started, paused and resumed
// with it (and paused when the connection drops, as the server pauses the
// talk then), so the file leaves the pauses out, like the server's PCM. One
// recorder per talk: it gives one continuous file when stopped. End talk
// stops it and sends the file with the request ("audio", multipart); so does
// Finish session while a talk goes on (through the confirm dialog's
// confirmBody). The server then stores it in place of its own recording. A
// talk that was going on when the page loaded has no recorder (a reload loses
// it): it ends without a file, and the server uses its own recording.
//
// The live voice feedback: every few seconds the live process analyses the
// last window of the talk's audio and sends {"type": "voice", "talk_id",
// "start_at", "end_at", "t", "voice_score", "pace", "pitch", "speaking_rate",
// "f0_range"} on the channel (live/Services/FeedbackService.py). Each one
// adds a point to the talk view's voice graph (pace solid, pitch variation
// dashed, at t seconds into the talk), updates the two cards and the
// "Updated ... ago" line, which counts from end_at (when that window was
// recorded) every second. A new talk starts the graph over.
//
// The status line says where it is: connecting, connected, reconnecting, or
// a stop. A connection that fails or
// drops, or a step that fails, starts over from 2 after a wait that grows
// from 1 s to 30 s (the live process pauses a recording talk meanwhile). It
// doesn't start over when the session isn't live (409 not_live) or the mic
// is blocked. Leaving the page closes it.
//
// The screen's state is screen.live, for what comes next (the talk buttons,
// the live feedback): sessionId, connection (the RTCPeerConnection), channel
// (the "control" data channel, null until it opens) and state ("connecting",
// "connected", "reconnecting", "stopped"). Nothing is kept in storage: the
// session is in the address, and a connection can't outlive a reload anyway.
document.addEventListener("DOMContentLoaded", function () {
    var screen = document.querySelector("[data-live-screen]");
    if (!screen) {
        return;
    }
    var live = screen.live = {
        sessionId: screen.dataset.sessionId,
        connection: null,
        channel: null,
        state: null,
    };
    var loading = screen.querySelector("[data-live-loading]");
    var content = screen.querySelector("[data-live-content]");
    var message = screen.querySelector("[data-live-message]");
    var status = screen.querySelector("[data-live-connection-status]");
    var statusText = status.querySelector("[data-live-connection-text]");
    var connectUrl = screen.dataset.connectUrl;
    var sessionContent = content.querySelector("[data-session-content]");
    var views = content.querySelectorAll("[data-live-view]");
    var sessionHeader = document.querySelector(".session-header:not([data-talk-header])");
    var talkHeader = document.querySelector("[data-talk-header]");
    var talkName = talkHeader.querySelector("[data-talk-name]");
    var talkStatus = talkHeader.querySelector("[data-talk-status]");
    var talkClock = talkHeader.querySelector("[data-talk-clock]");
    var pauseButton = document.getElementById("talk-pause");
    var endButton = document.getElementById("talk-end");
    var openTalk = null;  // the talk going on, from the session's JSON, or null
    var voice = {talkId: null, pace: [], pitch: [], endAt: null};  // the live voice graph's data
    var voiceChart = document.getElementById("live-voice-chart");
    var paceCard = document.getElementById("live-pace");
    var pitchCard = document.getElementById("live-pitch");
    var voiceUpdated = document.getElementById("live-voice-updated");
    var recorder = null;  // {talkId, media (the MediaRecorder), chunks} while a talk records here
    var kept = null;      // {talkId, blob}: a stopped recording whose request failed, sent again
    var clockTimer = null;
    var csrfToken = screen.dataset.csrfToken;
    var GATHER_MS = 5000;
    var FIRST_RETRY_MS = 1000;
    var MAX_RETRY_MS = 30000;
    var retryMs = FIRST_RETRY_MS;
    var retryTimer = null;
    var stream = null;  // the mic, kept across reconnects
    var attempt = 0;    // which connect() is current; an older one stops where it is
    var nextCommand = 1;
    var waiting = {};   // command id -> its callback, until the reply comes

    function setState(state, text) {
        live.state = state;
        status.dataset.state = state;
        statusText.textContent = text;
        loading.hidden = state === "connected";
        // The first time it is up: the session, fresh.
        if (state === "connected" && content.hidden) {
            content.hidden = false;
            screen.dataset.hasContent = "";
            refresh();
        }
    }

    // The session's JSON again (session.js draws the session view), then
    // the view and header for it.
    function refresh() {
        return sessionContent.session.refresh().then(show).catch(function (error) {
            console.warn(error);
            showMessage("Couldn't load the session. Reload the page.");
        });
    }

    // The talk view and header while a talk goes on, else the session's.
    function show(data) {
        openTalk = data.talks.find(function (talk) {
            return talk.status === "RECORDING" || talk.status === "PAUSED";
        }) || null;
        views.forEach(function (view) {
            view.hidden = view.dataset.liveView !== (openTalk ? "talk" : "session");
        });
        sessionHeader.hidden = Boolean(openTalk);
        talkHeader.hidden = !openTalk;
        clearInterval(clockTimer);
        if (!openTalk) {
            return;
        }
        var paused = openTalk.status === "PAUSED";
        talkName.textContent = "Talk " + openTalk.number;
        talkStatus.textContent = paused ? "Paused" : "Recording";
        talkStatus.classList.toggle("session-header-status-paused", paused);
        talkStatus.classList.toggle("session-header-status-recording", !paused);
        pauseButton.querySelector("[data-talk-pause-label=pause]").hidden = paused;
        pauseButton.querySelector("[data-talk-pause-label=resume]").hidden = !paused;
        tick();
        if (!paused) {
            clockTimer = setInterval(tick, 1000);
        }
    }

    // The talk's clock: the time recorded, without its pauses (one going on
    // included), "m:ss" or "h:mm:ss".
    function tick() {
        var now = Date.now();
        var seconds = (now - Date.parse(openTalk.started_at)) / 1000 - openTalk.paused_seconds
            - (openTalk.paused_at ? (now - Date.parse(openTalk.paused_at)) / 1000 : 0);
        seconds = Math.max(0, Math.floor(seconds));
        var hours = Math.floor(seconds / 3600);
        var minutes = Math.floor(seconds % 3600 / 60);
        talkClock.textContent = (hours ? hours + ":" + String(minutes).padStart(2, "0") : minutes)
            + ":" + String(seconds % 60).padStart(2, "0");
    }

    function showMessage(text) {
        message.textContent = text;
        message.hidden = !text;
    }

    // Sends a command on the channel; reply(data) gets the live process's
    // answer. False when the channel isn't open (nothing sent).
    function send(type, reply) {
        if (!live.channel || live.channel.readyState !== "open") {
            showMessage("Not connected yet. Wait for the connection, then try again.");
            return false;
        }
        var id = nextCommand++;
        waiting[id] = reply;
        live.channel.send(JSON.stringify({id: id, type: type}));
        return true;
    }

    // Stops for good: nothing more to try until the page is reloaded.
    function stop(text) {
        clearTimeout(retryTimer);
        closePeer();
        setState("stopped", text);
    }

    function closePeer() {
        if (live.connection) {
            live.connection.close();
        }
        live.connection = null;
        live.channel = null;
        // Commands still waiting won't get their reply on this channel.
        Object.keys(waiting).forEach(function (id) {
            var reply = waiting[id];
            delete waiting[id];
            reply({type: "error", detail: "The connection dropped. Try again once it's back."});
        });
    }

    function retry() {
        // The server pauses the talk on a drop: the recording pauses with it.
        if (recorder && recorder.media.state === "recording") {
            recorder.media.pause();
        }
        closePeer();
        setState("reconnecting", "Reconnecting…");
        clearTimeout(retryTimer);
        retryTimer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
    }

    // The answer from Django as JSON; an error answer throws with its status and code.
    function request(options) {
        return fetch(connectUrl, Object.assign({credentials: "same-origin"}, options)).then(function (response) {
            if (response.status === 204) {
                return null;
            }
            return response.json().catch(function () {
                return {};
            }).then(function (data) {
                if (!response.ok) {
                    var error = new Error((data.errors && data.errors.__all__ && data.errors.__all__[0])
                        || "Connect failed: " + response.status);
                    error.status = response.status;
                    error.code = data.code;
                    throw error;
                }
                return data;
            });
        });
    }

    // Resolves once every ICE candidate is in the local description, or after GATHER_MS.
    function gathered(peer) {
        return new Promise(function (resolve) {
            if (peer.iceGatheringState === "complete") {
                resolve();
                return;
            }
            var timer = setTimeout(resolve, GATHER_MS);
            peer.addEventListener("icegatheringstatechange", function () {
                if (peer.iceGatheringState === "complete") {
                    clearTimeout(timer);
                    resolve();
                }
            });
        });
    }

    function connect() {
        var mine = ++attempt;
        var peer = null;
        if (live.state !== "reconnecting") {
            setState("connecting", "Connecting…");
        }
        request({headers: {"Accept": "application/json"}})
            .then(function (offer) {
                if (mine !== attempt) {
                    return null;
                }
                peer = new RTCPeerConnection({
                    iceServers: offer.ice_servers,
                    iceTransportPolicy: offer.ice_transport_policy,
                });
                live.connection = peer;

                peer.addEventListener("connectionstatechange", function () {
                    if (live.connection !== peer) {
                        return;  // replaced or closed already
                    }
                    if (peer.connectionState === "connected") {
                        retryMs = FIRST_RETRY_MS;
                        setState("connected", "Connected");
                    } else if (peer.connectionState === "failed" || peer.connectionState === "disconnected") {
                        retry();
                    }
                });
                peer.addEventListener("datachannel", function (event) {
                    if (live.connection === peer && event.channel.label === "control") {
                        live.channel = event.channel;
                        live.channel.addEventListener("message", function (message) {
                            var data;
                            try {
                                data = JSON.parse(message.data);
                            } catch (error) {
                                return;
                            }
                            if (data.type === "voice") {
                                showVoice(data);
                                return;
                            }
                            var reply = waiting[data.id];
                            delete waiting[data.id];
                            if (reply) {
                                reply(data);
                            }
                        });
                    }
                });

                return peer.setRemoteDescription({type: "offer", sdp: offer.sdp})
                    .then(function () {
                        // addTrack takes the offer's audio transceiver (it has no
                        // track yet), so the mic goes out on the one the live
                        // process receives on.
                        stream.getAudioTracks().forEach(function (track) {
                            peer.addTrack(track, stream);
                        });
                        return peer.createAnswer();
                    })
                    .then(function (answer) {
                        return peer.setLocalDescription(answer);
                    })
                    .then(function () {
                        return gathered(peer);
                    })
                    .then(function () {
                        if (mine !== attempt || live.connection !== peer) {
                            return null;
                        }
                        return request({
                            method: "POST",
                            headers: {"Accept": "application/json", "Content-Type": "application/json",
                                      "X-CSRFToken": csrfToken},
                            body: JSON.stringify({sdp: peer.localDescription.sdp}),
                        });
                    });
            })
            .catch(function (error) {
                if (mine !== attempt) {
                    return;
                }
                if (error.code === "not_live") {
                    stop("This session isn't live any more.");
                    return;
                }
                console.warn(error);
                retry();
            });
    }

    // A command from a button: the button waits for the reply, then the screen
    // follows the new state (or the refusal shows).
    // One live voice window: a point on each line, the cards, the time.
    function showVoice(data) {
        if (voice.talkId !== data.talk_id) {
            voice = {talkId: data.talk_id, pace: [], pitch: [], endAt: null};
        }
        if (data.pace !== null) {
            voice.pace.push([data.t, data.pace]);
        }
        if (data.pitch !== null) {
            voice.pitch.push([data.t, data.pitch]);
        }
        voice.endAt = Date.parse(data.end_at);
        if (voiceChart && voiceChart.timeline) {
            voiceChart.timeline.setData(voice.pace, null, voice.pitch);
        }
        updateCard(paceCard, data.pace, data.speaking_rate === null ? "\u2013" : data.speaking_rate.toFixed(1) + " syl/s",
                   ["Too slow", "On pace", "Too fast"]);
        updateCard(pitchCard, data.pitch, data.f0_range === null ? "\u2013" : Math.round(data.f0_range) + " Hz",
                   ["Flat", "Lively", "Too varied"]);
        updateVoiceTime();
    }

    // A voice card (voice_measure.html): the score (-10 to +10) places its
    // dot (--score), with the raw value and a word for it: low, fine
    // (-5 to +5), high.
    function updateCard(card, score, raw, words) {
        if (!card || score === null) {
            return;
        }
        card.style.setProperty("--score", score);
        card.querySelector(".voice-measure-score").textContent = (score > 0 ? "+" : "") + score.toFixed(1);
        card.querySelector(".voice-measure-raw").textContent = raw;
        var status = card.querySelector(".live-status");
        var fine = Math.abs(score) <= 5;
        status.textContent = score < -5 ? words[0] : fine ? words[1] : words[2];
        status.classList.toggle("good", fine);
        status.classList.toggle("warn", !fine);
    }

    // "Updated 3 s ago", from when the last window was recorded.
    function updateVoiceTime() {
        if (!voiceUpdated || voice.endAt === null) {
            return;
        }
        var seconds = Math.max(0, Math.round((Date.now() - voice.endAt) / 1000));
        voiceUpdated.textContent = "Updated " + seconds + " s ago";
    }
    setInterval(updateVoiceTime, 1000);

    // The talk's recording starts: a new recorder on the mic.
    function startRecording(talkId) {
        if (typeof MediaRecorder === "undefined" || !stream) {
            return;  // no recorder in this browser: the server's recording is used
        }
        var media = new MediaRecorder(stream);
        var chunks = [];
        media.addEventListener("dataavailable", function (event) {
            if (event.data.size) {
                chunks.push(event.data);
            }
        });
        // A chunk a second, so a long talk isn't one buffer at the end.
        media.start(1000);
        recorder = {talkId: talkId, media: media, chunks: chunks};
    }

    // The talk going on's recording, stopped: a promise of
    // {blob, name} (the file to send), or null with none recorded here.
    function stopRecording() {
        if (!openTalk) {
            return Promise.resolve(null);
        }
        if (kept && kept.talkId === openTalk.id) {
            return Promise.resolve(kept);
        }
        if (!recorder || recorder.talkId !== openTalk.id) {
            return Promise.resolve(null);
        }
        var stopping = recorder;
        recorder = null;
        return new Promise(function (resolve) {
            stopping.media.addEventListener("stop", function () {
                var type = stopping.media.mimeType || "audio/webm";
                var extension = type.indexOf("mp4") !== -1 ? "m4a" : type.indexOf("ogg") !== -1 ? "ogg" : "webm";
                kept = {talkId: stopping.talkId, blob: new Blob(stopping.chunks, {type: type}),
                        name: "talk." + extension};
                resolve(kept);
            }, {once: true});
            stopping.media.stop();
        });
    }

    // The request body with the recording in "audio", or null without one.
    function recordingBody() {
        return stopRecording().then(function (recording) {
            if (!recording) {
                return null;
            }
            var body = new FormData();
            body.append("audio", recording.blob, recording.name);
            return body;
        });
    }

    // ok(reply), when given, runs on the live process's ok, before the refresh.
    function command(button, type, failed, ok) {
        showMessage("");
        button.disabled = true;
        var sent = send(type, function (reply) {
            button.disabled = false;
            if (reply.type !== "ok") {
                showMessage(reply.detail || failed);
                return;
            }
            if (ok) {
                ok(reply);
            }
            refresh();
        });
        if (!sent) {
            button.disabled = false;
        }
    }

    // Start talk: the session header's and the talks card's.
    document.querySelectorAll("#session-start-talk, #talks-start-talk").forEach(function (button) {
        button.addEventListener("click", function () {
            command(button, "start_talk", "Couldn't start the talk.", function (reply) {
                startRecording(reply.talk.id);
            });
        });
    });

    pauseButton.addEventListener("click", function () {
        if (openTalk && openTalk.status === "PAUSED") {
            command(pauseButton, "resume_talk", "Couldn't resume the talk.", function () {
                if (recorder && recorder.media.state === "paused") {
                    recorder.media.resume();
                }
            });
        } else {
            command(pauseButton, "pause_talk", "Couldn't pause the talk.", function () {
                if (recorder && recorder.media.state === "recording") {
                    recorder.media.pause();
                }
            });
        }
    });

    // End talk: over HTTP, not the channel (the talk is finished in Django,
    // which then stops its recording in the live process).
    endButton.addEventListener("click", function () {
        if (!openTalk) {
            return;
        }
        showMessage("");
        endButton.disabled = true;
        var url = openTalk.finish_url;
        recordingBody()
            .then(function (body) {
                return fetch(url, {
                    method: "POST",
                    headers: {"Accept": "application/json", "X-CSRFToken": csrfToken},
                    body: body || undefined,
                });
            })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().catch(function () {
                        return {};
                    }).then(function (data) {
                        throw new Error((data.errors && data.errors.__all__ && data.errors.__all__[0])
                            || "Couldn't end the talk.");
                    });
                }
                kept = null;  // sent and stored
                return refresh();
            })
            .catch(function (error) {
                showMessage(error.message);
            })
            .finally(function () {
                endButton.disabled = false;
            });
    });

    // Finish session (either header): the confirm dialog sends the talk's
    // recording with it, if a talk is going on and recorded here.
    document.querySelectorAll("#session-finish, #talk-finish-session").forEach(function (button) {
        button.confirmBody = recordingBody;
    });

    setState("connecting", "Connecting…");
    navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false},
        video: false,
    })
        .then(function (mic) {
            stream = mic;
            connect();
        })
        .catch(function (error) {
            console.warn(error);
            stop("No microphone: allow it for this site and reload the page.");
        });

    window.addEventListener("pagehide", function () {
        clearTimeout(retryTimer);
        attempt += 1;
        closePeer();
        if (stream) {
            stream.getTracks().forEach(function (track) {
                track.stop();
            });
        }
    });
});
