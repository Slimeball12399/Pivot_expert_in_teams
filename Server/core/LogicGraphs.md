# State Machine
## Session

```mermaid
stateDiagram-v2
    direction LR
    [*] --> NOT_STARTED : create
    NOT_STARTED --> LIVE : start / set started_at
    NOT_STARTED --> CANCELLED : cancel
    LIVE --> FINISHED : end, or no reconnect within 10 min / set ended_at
    LIVE --> ABORTED : abort [connection timeout] / set ended_at
    FINISHED --> DELETED : delete / discard its talks (out of progress, the rows stay)
    FINISHED --> [*]
    DELETED --> [*]
    CANCELLED --> [*]
    ABORTED --> [*]
    note right of LIVE : Devices can connect. A talk needs an active connection.
```

## Talk

```mermaid
stateDiagram-v2
    direction LR
    [*] --> RECORDING : start_talk [session LIVE and connection available] / set started_at
    RECORDING --> PAUSED : pause or connection lost
    PAUSED --> RECORDING : resume [connection available]
    RECORDING --> PROCESSING : finish / set duration, upload audio
    PAUSED --> PROCESSING : finish / set duration, upload audio
    RECORDING --> DISCARDED : discard
    PAUSED --> DISCARDED : discard
    RECORDING --> FAILED : upload failed, or no reconnect within 10 min
    PAUSED --> FAILED : no reconnect within 10 min
    PROCESSING --> COMPLETED : analysis_done / save voice results
    PROCESSING --> FAILED : analysis_failed / set error
    FAILED --> PROCESSING : retry [audio exists]
    COMPLETED --> DISCARDED : discard
    COMPLETED --> [*]
    DISCARDED --> [*]
```

## Flow

Session and talk state machines merged. Solid arrows are trainer actions, dotted arrows are the system (WebRTC layer, analysis worker). Double-bordered boxes are sub-flows, described in their own sections below.

```mermaid
flowchart LR
    A([Trainer creates session]) --> S1[Session NOT_STARTED]
    S1 -->|cancel| SC([Session CANCELLED])
    S1 -->|start| S2[Session LIVE]

    S2 --> C[[Establish connection]]
    C -.->|failed / timeout| SA([Session ABORTED])

    C -->|connected: start or resume talk| T1[[Talk RECORDING with live feedback]]
    T1 -->|pause| T2[Talk PAUSED]
    T2 -->|resume| T1
    T1 -->|discard| TD([Talk DISCARDED])
    T2 -->|discard| TD
    T1 -.->|connection lost: talk PAUSED| C

    T1 -->|finish| P[[Process talk]]
    T2 -->|finish| P
    P -.->|done| T4([Talk COMPLETED])
    P -.->|failed| T5[Talk FAILED]
    T5 -->|retry| P
    T5 -->|discard| TD
    T4 -->|discard| TD

    P -->|trainer continues| N{Another talk?}
    N -- yes --> C
    N -- no --> E[end]
    E --> SF([Session FINISHED])
```

Processing runs in the background, so the trainer can start the next talk without waiting for the analysis. If the connection drops during a talk, the talk is paused and the flow goes back to establishing the connection; once reconnected the talk resumes; if the trainer doesn't reconnect within 10 minutes the session is finished and the talk fails.

### Establish connection

Split in two: UDP for the board telemetry and WebRTC for the trainer and speaker devices. "Connected" means both are up.

#### UDP (board telemetry)

Separate diagram, to do.

#### WebRTC

UML sequence diagram. Solid arrows are requests, dashed arrows are replies, open arrowheads are asynchronous messages (streams). Django only does signaling over HTTP; media goes directly between the browsers and the WebRTC peer.

```mermaid
sequenceDiagram
    actor T as Trainer (browser)
    participant API as Server (Django)
    participant RTC as WebRTC peer
    actor U as Speaker (mobile / browser)

    T->>API: start session
    API->>API: check trainer, set session LIVE
    API->>RTC: open session (session id)

    Note over T,RTC: Trainer connection (audio in)
    RTC-->>API: offer for trainer (SDP)
    API-->>T: offer (SDP)
    T->>API: answer (SDP)
    API->>RTC: trainer answer
    T-)RTC: audio stream
    RTC-)T: live feedback

    Note over API,U: Speaker connection (output only)
    U->>API: join (session id)
    API->>API: check user is the session's speaker
    API->>RTC: create speaker peer
    RTC-->>API: offer (SDP)
    API-->>U: offer, shown as join popup
    U->>API: answer (SDP) = accept
    API->>RTC: speaker answer
    RTC-)U: live feedback

    opt Connection lost
        RTC->>API: connection lost (session id, peer)
        RTC->>RTC: wait for reconnect
        alt Reconnected before timeout
            RTC-)U: live feedback resumes
        else Timeout
            RTC->>API: timeout
            API->>API: abort session
        end
    end
```

### Talk with live feedback

### Process talk

Runs after the whole talk is recorded. The live partial results are handled in Talk with live feedback, not here.

```mermaid
flowchart LR
    subgraph Browser[Trainer browser]
        A([Talk finished]) --> K[Keep local recording]
        K --> B[Upload full lossless audio]
        L[Delete local recording]
    end
    subgraph Server[Server]
        C[Save audio as File] --> S[Confirm: audio saved]
        S --> D[Talk PROCESSING]
        D --> E[Queue analysis job]
    end
    subgraph Worker[Job worker]
        F[Run full voice analysis] --> G[Save FullVoiceResult]
        G --> H[Score using speaker profile: age, sex]
        H --> I([Talk COMPLETED])
    end

    B --> C
    S --> L
    E --> F
    B -->|failed: retry, max 3| B
    F -->|failed: retry, max 3| F
    H -->|failed: retry, max 3| H
    B -->|failed 3 times| X[Talk FAILED + error]
    F -->|failed 3 times| X
    H -->|failed 3 times| X
    X -->|trainer retry| R{Audio saved?}
    R -- yes --> F
    R -- no --> B
```

The browser keeps the recording until the server confirms it is saved, so a failed upload never loses audio. Each step retries automatically up to 3 times (with growing waits) before the talk is FAILED; after that the trainer can retry by hand, starting from the first unfinished step. How jobs are picked up (Django tasks, Celery, ...) is still open.
