# Enginnering Decisions
### Scoring
Score | Meaning
--- | ---
1 | Poor
2 | Below average
3 | Average
4 | Above average
5 | Excelent

## Platform
Criterion | Weight | Mobile | Desktop | Web 
--- | --- | --- | --- |--- 
Cross-Platform Accessibility | 20% | 3 | 2 | 5
Cost Efficiency | 10% | 4 | 1 | 5
Functional suitability | 10% | 4 | 1 | 4 
Maintanace & Reliability | 15% | 3 | 1 | 5
Interaction capability | 20% | 4 | 4 | 3
Compatibility | 15% | 5 | 4 | 2
Performance efficiency | 5% | 3 | 5 | 1
Security | 5% | 3 | 2 | 5
TOTAL | 100% | 3.7 | 2.5 | 3.85

### Why

Read across the eight criteria, the scoring does not point to a single winning platform so much as it separates by user role: the criteria that matter most for the trainer-facing application favour Web, and the criteria that matter most for the athlete's in-session and device-configuration use favour Mobile. The table supports the split the team agreed on, the athlete uses the mobile app, the trainer uses the web app, rather than one platform being chosen over the other.

**Cross-Platform Accessibility** favours Web because a trainer needs to open the tool on whatever device is available at a given venue, a laptop, a shared PC, or a TV in a training room, without requiring an install. Mobile needs a platform-specific install, which is reasonable for an athlete's own phone but does not fit the trainer's use case as well. Desktop scores lowest, since it needs a per-device install and offers no particular advantage for either role.

**Cost Efficiency** favours Web as the cheaper, single-codebase option to build and maintain as the trainer-facing tool. Mobile scores close behind: a native app is needed regardless for device configuration, but that native integration is what makes it more expensive to build, and it is not something the athlete can view while practicing. Desktop scores lowest, requiring a separate installer per operating system for a role that neither the trainer nor the athlete strictly needs.

**Functional suitability** ties Mobile and Web because each is doing a different, necessary job: Mobile handles the athlete's device-level integration with the board, and Web handles the trainer running and displaying training sessions. Desktop scores poorly because it does not add any function that is not already covered by one of the other two, adding a third platform to maintain for no additional capability.

**Maintenance & Reliability** favours Web: a single deployable application updates for every trainer at once, which suits a tool one team maintains across multiple users. Mobile is behind, since it requires users to update their app manually, unlike a single web deployment that updates for everyone at once. Desktop scores lowest, needing three separate operating-system builds kept working, with no corresponding role that justifies the extra maintenance.

**Interaction capability** ties Mobile and Desktop above Web. For Mobile, this matters specifically for the athlete: a handheld device with touch, camera, and sensor access supports live feedback during calibration and while practicing in a way a browser cannot fully replicate, since browsers restrict access to some native device features.

**Compatibility** favours Mobile directly because of the athlete's role: phones ship with the Bluetooth and WiFi radios needed to pair with the board, which is the mobile app's actual job. Desktop scores close behind, since most laptops carry similar hardware. Web scores lowest, since browser support for device pairing is inconsistent across browsers, making it the least reliable option for the one task Mobile exists to handle.

**Performance efficiency** favours Desktop, with dedicated hardware and no browser overhead. This is the lowest-weighted criterion in the table, and Desktop's win here does not correspond to a need in either the trainer's or the athlete's role, which is part of why Desktop is excluded despite leading on this one criterion. Mobile is capable but constrained by battery and thermal limits. Web scores lowest, due to the overhead of running inside a browser runtime.

**Security** favours Web: centralising authentication and session data server-side over HTTPS keeps sensitive data off the client device, a standard way of reducing client-side attack surface, which fits a tool where a trainer accesses data belonging to multiple athletes. Mobile is behind, since some data is necessarily cached locally to support device pairing, which is exposed if the device is lost. The smaller gap to Desktop is less certain: both platforms cache some data locally, and without a specific reference for shared-device usage in this context, the lower Desktop score should be read as reflecting an assumption, that a shared or practice-room computer is more likely to be left signed in, rather than an established technical difference between the two.

**Decision:** The scoring supports the split already agreed on rather than choosing one platform outright. Web is used for the trainer-facing application, since it leads on the criteria that matter for that role: Cross-Platform Accessibility, Cost Efficiency, Maintenance & Reliability, and Security. Mobile is used for the athlete facing application, since it leads on the criteria that matter for that role: Compatibility and Interaction capability, and is required regardless for device pairing under Functional suitability. Desktop is excluded entirely: it does not lead on any criterion that serves either role, and its one win, Performance efficiency, is the lowest-weighted criterion in the table.

- Ok so no booking system is really needed it might be obsolete -> 
- Mobile app with user profile, their results, and configing the device from admin account -> user account control -> Possibly mathching based on voice
- Web is for running the training etc 



### Refs
- https://www.3appes.com/web-vs-mobile-vs-desktop/
- https://blog.pacificcert.com/iso-25010-software-product-quality-model/

## Backend server
Criterion | Weight | Django | Laravel | FastAPI | Node.js | .ASP.NET Core 
--- | --- | --- | --- | --- |--- | --
Maintainability | 5% | 5 | 5 | 2 | 3 | 3
Team Familiarity | 10% | 5 | 4 | 3 | 3 | 2
Function set | 10% | 5 | 5 | 2 | 3 | 4
Security | 5% | 5 | 5 | 1 | 1 | 4
Flexibility | 10% | 2 | 2 | 5 | 5 | 3 
Integration | 20% | 3 | 2 | 3 | 5 | 4
Data Processing Capabilities | 15% | 5 | 1 | 5 | 2 | 3
Visualization | 15% | 5 | 2 | 5 | 5 | 3
Performance | 10% |  2 | 3 | 3 | 4 | 5 
TOTAL | 100% | 4 | 2.75 | 3.55 | 3.75 | 3.45

### Why

**Maintainability.** Django and Laravel both max out because they're "batteries included": the framework enforces a project structure and conventions, so the codebase stays consistent as more people touch it. FastAPI scores low since it's minimal by design, leaving structural decisions to us, which tends to drift as the project grows. Node.js sits in the middle mainly because it's inherently minimal, teams have to choose their own structure on top of it, which can work but doesn't enforce consistency the way Django or Laravel do. .ASP.NET Core also lands in the middle, but for a different reason: it does provide built-in conventions of its own (MVC structure, dependency injection), so the mid-range score here reflects our limited hands-on experience with it rather than a lack of structure in the framework itself.

**Team Familiarity.** This one just reflects what the team already knows. Django scores highest since it's the framework we have the most prior experience with, Laravel is close behind, FastAPI and Node.js are average, and .ASP.NET Core is lowest since it's the one we know least.

**Function set.** Django and Laravel tie for the win because both ship with a lot out of the box: ORM, auth, admin tooling, so less has to be built or bolted on ourselves. FastAPI scores worst since it's just routing and validation and leaves the rest to us. Node.js needs external packages for most of it, and .ASP.NET Core has a decent built-in set but not as all-in-one as Django or Laravel.

**Security.** Django and Laravel win on mature, built-in security defaults: CSRF protection, auth, and an ORM that avoids raw-SQL injection by default, which matters since we don't have a dedicated security person. FastAPI and Node.js score worst not because they're insecure by design, but because these specific protections, CSRF handling, session/auth scaffolding, an ORM that guards against raw-SQL injection, aren't built in and have to be added and configured by the developer, which leaves more room for a student team without dedicated security expertise to miss something. .ASP.NET Core also does well on built-in security, it's just less familiar to us.

**Flexibility.** FastAPI and Node.js win precisely because they're unopinionated, letting us structure the app how we want that fits the project. Django and Laravel score worst here for the same reason they won Maintainability and Function set: enforcing a way of doing things is the trade-off for that structure. .ASP.NET Core lands in the middle.

**Integration**, the highest-weighted criterion. Node.js wins clearly: its ecosystem and native async I/O are built around handling many concurrent connections and real-time data, which matters for streaming data in from the board. .ASP.NET Core is next. Django and FastAPI are only average here, and Laravel is worst since PHP's ecosystem isn't built around this kind of integration work.

**Data Processing Capabilities.** Django and FastAPI tie for the win because they're both Python, giving direct access to Python's data and numerical ecosystem (numpy, pandas, etc.), which is directly relevant since we're processing voice and sensor data. Laravel is worst, PHP has nothing comparable. Node.js is also weak here for the same reason, and .ASP.NET Core is average.

**Visualization.** Django, FastAPI, and Node.js all score well. Python again benefits from its plotting and analysis libraries, and Node.js benefits from the JS charting ecosystem that a web frontend would consume directly. Laravel is worst, and .ASP.NET Core is average.

**Performance.** .ASP.NET Core wins, running on .NET's JIT-compiled runtime gives it an edge over the interpreted runtimes the other options run on, with Node.js close behind thanks to async I/O. FastAPI and Laravel are average, and Django is worst: the "batteries included" overhead that helps Maintainability and Function set costs it here.

**Decision:** Django wins overall not because it dominates any single criterion but because it scores at or near the top on the most criteria: Maintainability, Team Familiarity, Function set, Security, Data Processing Capabilities, and Visualization all favour it, and the last two matter directly since voice and movement analysis is the core of what this product does. Node.js is the closest competitor almost entirely because it wins Integration, which happens to be the single highest-weighted criterion, real-time board data handling is a genuine strength of Node.js, and it is worth naming as the main thing Django gives up. Django's advantage on Data Processing Capabilities and Visualization directly serves the analysis side of the product, and combined with the team's existing familiarity with it and its stronger default security, it is the safer overall choice than trading that breadth for a single integration-focused win. Laravel is ruled out for the same reason it loses on Integration and Data Processing, a PHP framework does not fit a data-analysis-heavy backend. FastAPI and .ASP.NET Core both land in between without leading anywhere important enough to change the outcome.

**Note:** the team has limited hands-on experience with .ASP.NET Core, so its scores are based on team discussion and a brief review rather than direct familiarity, unlike the other four options.

### Refs
- https://blog.pacificcert.com/iso-25010-software-product-quality-model/

## Databases
**What  is the data**
- Structured User data
- Analysis? - We dont know what yet
- Raw sound (wav)
- Movemenet (Raw position feeds etc)

Separation of concerns decison | Relational DB | Relational DB + S3 | Relational + S3 + Time series
-- | -- | -- | --
Setup | Easy | Straight forward | Multiple possibilities and configuration
Fits data | Forced | Yes | Yes
Query Flexibility | Slow relational | Only structured data | Easy access
Data consistency | Rule based strict | Some consideration required | Hard to maintain
Performance | Slow for sensory | Slow for multiple sources but fast retrival on one | Fast
Scalability | Standard | Analysis requires the files to be held in memory | Best for analysis
Data protection | Easy | Ok | Difficult because of consistency 
Fun | Nah | Meh | Yes

Tripple setup
****
**Structured data**  
Well its not much different between what tech we choose experience determines decion between DBs

****
**Sensor Data**  
Wav is probably only storable as file in raw format while sensory data can be bot raw file or time seriesed. As mentioned above the separation depends on that decision in case we do time seriesed we can probably either do a module on the relational db that would probably reduce complexity or do a separate time seriesed database  
If we do files analysis of multiple files are difficult since multiple files needs to be read and constant reading is required 

### Why

**Decision:** We're going with the triple setup (Relational + S3 + Time series). Technically it already wins on the criteria that reflect what the data actually needs. It fits data, query Flexibility, Performance, and Scalability so it's not purely a "fun" pick. Relational-only and relational+S3 don't teach us anything we haven't already practiced, while a time series database is something none of us have hands-on experience with. We're accepting the worst Setup complexity and worst Data protection/consistency difficulty of the three options in exchange for that, both because the data genuinely fits better, and because we want the added challenge and the experience of working with a time series database this semester.

### Refs 
- https://www.youtube.com/watch?v=69Tzh_0lHJ8
- https://www.influxdata.com/time-series-database/


## Processing delegation
What standard do we wanna use for communication
1. **Process on board** - The board sens the data that needs to be visualized out to server or device not much processing outside
2. **Server processes** - Data is sent to the server from the board than sent back to display after analysis
3. **Mobile processes** - The mobile device processes the data only send data to server after analysis
4. **Stream to both** - The device streams to server and mobile at the same time mobile visualizes server does porcessing
5. **Mobile as gateway** - Mobile gets raw data shows non processing data directly than send all to the server for analysis

| Criterion | Weight | 1. Process on board | 2. Server processes | 3. Mobile processes | 4. Stream to both | 5. Mobile as gateway |
|---|---|---|---|---|---|---|
| Performance | 10% | 1 | 5 | 2 | 5 | 3 |
| Latency | 20% | 5 | 3 | 4 | 4 | 2
| Ease of implementation | 10% | 1 | 5 | 2 | 2 | 4
| User experience | 10% | 1 | 3 | 1 | 4 | 3 | 2
| Reliability (network dependence) | 15%  | 5 | 3 | 3 | 4 | 1 |
| Hardware requirements (board) | 15% | 1 | 5 | 5 | 3 | 5 |
| Power / battery usage | 20% | 3 | 5 | 1 | 3 | 3 |
| Number of to mobile | 1 | 1 | 2 | 1 | 1-2 | 3
| **Total** | **100%** | 2.8 | 4.1 | 2.7 | 3.55 | 2.9 |

### Why

**Performance** ties Server processes and Stream to both at the top, since both hand the heavy analysis to the server, which has far more compute available than the board or a phone. 

**Latency** favours Process on board, since results appear without a network round trip, the data is processed quickly. Mobile as gateway scores lowest, raw data has to reach the phone and then be forwarded again to the server before any result comes back, two hops instead of one.

**Ease of implementation** favours Server processes, a single server-side analysis pipeline is the standard client-server pattern the team already has experience with. Process on board scores lowest, real-time processing on embedded hardware requires specialised low-level coding skills the team does not currently have.

**User experience** favours Stream to both, the mobile side can show something immediately from the raw stream while the server works on the deeper analysis in parallel, rather than the user waiting on one path for everything.

**Reliability (network dependence)** favours Process on board, since it keeps working without a network connection, nothing is sent out to fail on the way. Mobile as gateway scores lowest, it depends on two connections holding, phone to board and phone to server, so there are more points where it can break.

**Hardware requirements (board)** favours every option that keeps the analysis off the board (Server processes, Mobile processes, Mobile as gateway), since the board itself only has to move data rather than run the compute-heavy processing. Process on board scores lowest for the same reason, it demands the most capable and expensive board hardware, at a stage where the hardware isn't yet built to spec.

**Power / battery usage** favours Server processes, offloading the heavy analysis to a mains-powered server is more power-efficient than making a battery-constrained device do it. Mobile processes scores lowest, running sustained analysis on the phone drains its battery fastest of any option.

**Decision:** Server processes wins overall not by dominating every criterion, but by winning or tying the top score on the two highest-weighted ones it's actually built for, Power / battery usage and (tied) Performance, while also being the easiest to implement given the team's existing server-side experience. It gives up Latency and Reliability to Process on board, but Process on board is ruled out anyway by its Hardware requirements score, the board isn't at a stage where it can realistically carry that processing load. Stream to both is the closest competitor and wins User experience, but its added complexity, two simultaneous data paths to coordinate, is exactly what costs it on Ease of implementation, and it doesn't lead on the highest-weighted criteria the way Server processes does.

## Communication with the board
| Criterion | Weight | 1. BLE | 2. WIFI |
|---|---|---|---|
| Latency |20% |3|4|
| Throughput |20%|1|5|
| Time to connect |10%|4|2|
| Connection stability |20%|3|4|
| Range |5%|2|3|
| Data integrity |15% |4|4|
| Power usage |5%|5|2|
| Protocol complexity|5%|4|3|
| **Total**|**100%**|2.95|3.85|

BLE ideally suited for initial configuration and WIFI for server communication

## Wifi data streaming approaches

-UDP - Acceptable loss at transit for better latency (live dashboard monitoring)

-TCP - Data completeness over latency for analysis

| Criterion | Weight | 1. UDP live + TCP at session end | 2. UDP live + TCP at intervals | 3. Single Websocket channel | 4. UDP live + continuous TCP upload | 5. MQTT | 6. gRPC bidirectional stream | 7. Preprocessing on Chip (paired with any before) |
|---|---|---|---|---|---|---|---|---|
| Real-time displaying |20% | 5 | 5 | 3 | 5 | 4 | 4 | - |
| Near Real-time analysis |10% | 1 | 3 | 3 | 5 | 4 | 5 | +1 |
| On-device complexity | 10% | 2 | 3 | 2 | 4 | 3 | 4 | -2 |
| Server complexity |10%| 2 | 3 | 2 | 3 | 4 | 3 | +1 |
| Jitter / possible delay |15% | 4 | 3 | 2 | 5 | 4 | 5 | +1 |
| Data completeness |20% | 5 | 4 | 5 | 5 | 4 | 5 | -1 |
| Power consumption |5% | 4 | 3 | 3 | 1 | 3 | 1 | -1 |
| Local (on-device) storage | 5% | 1 | 2 | 3 | 5 | 3 | 4 | +1 |
| Security |5% | 3 | 3 | 4 | 3 | 5 | 5 | 0 |
| **Total**|**100%**|3.5|3.55|3.10|4.4|3.85|4.25|-0.05|

Worth checking -> are we actually able to implement real-time analysis even if we have the data?



## AI
- Desing comparison - Used to higlight missed points, identify additional pros const for certain decisions such as frameworks, architectures
- Code analysis - It is used to understand unfamiliar code, hilgight errors or potential shortcomings, support with bug resolution, hihglight deviation from coding standards
- Test case generation - Used to suggest and generate test cases for the project based on predefined requiremetns
- Diagram generation assitance - Used to help with syntax and plotting engineering designs made by the student
- Documentation search - It helps with searching for sintax or technonolgy relevant questions in order to speed up understanding 
- Boilerplate & Small code completion - AI is used to help complete repetitive boilerplate code as well as configuration files data models or sceletons

### Musts
- All code is resposibility of contributor
- Every line has to be explainable by the contributor
- Decisions must be rooted in references or engineering knowledge