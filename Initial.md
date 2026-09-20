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

**Cross-Platform Accessibility** 
Web just needs a link/browser, no install, so a trainer can pull it up on any TV/laptop and a user on any phone. 
Mobile needs an OS-specific install (iOS/Android split), which is still fine but a step behind. Desktop is worst here since it needs a per-OS install.

**Cost Efficiency** 
Cost efficientcy the mobile is needed to configure the board and functially can allow for more integration but its higher cost to develop and you cannot look at it while practicing.
Web is the cheapest, and fastest. Desktop is worst, separate installers/builds per OS for a feature set.

**Functional suitability** 
Mobile and Web tie because both cover what we actually need: Mobile for device-level integration (talking to the board),
Web for running/displaying training sessions. 
Desktop scores poorly because we think it'ss just not actually suitable

**Maintenance & Reliability**
Web wins because it's one deployable that updates instantly for every user, easy to maintain as a team. 
Mobile is behind because OS updates and user needs to update manually to get the latest update. 
Desktop is worst, three separate OS builds (Windows/Mac/Linux) to keep working and we still need user to manually update if the desktop has new version.

**Interaction capability**
Mobile and Desktop tie: Both are good for live feedback during calibration. Web is behind because browsers restrict access to some native device features, so the in-session interaction is less rich than either native option.

**Compatibility**
Mobile wins because phones ship with the Bluetooth/WiFi radios needed to pair with the board directly. Desktop is close since most laptops also have that hardware. Web is not very good, because browser support for device pairing are generally inconsistent across browsers, so it's the least reliable option for actually talking to the board.

**Performance efficiency**
Desktop wins with dedicated hardware and no browser overhead, best for real-time processing/visualization. Mobile is capable but constrained by battery/thermal limits. Web is worst because it doesnt deliver the native experience.

**Security** 
Web wins because auth/data stays server-side over HTTPS with nothing sensitive stored on the device. Mobile is behind since tokens/data cached locally are exposed if the device is lost. Desktop is worst, sessions run on shared/practice-room computers are more likely to stay logged in or expose data to the next person using the machine.

**Decision:** Web is prioritized as the platform for MVP - it wins the criteria we weighted highest (Accessibility, Maintenance, Cost, Security) and those map directly to what an MVP needs: something cheap to build and easy to keep running for a small 3 student team. Desktop is dropped entirely, it doesn't lead on anything except the lowest-weighted criterion (Performance) and costs the most to maintain. Mobile stays in scope alongside Web (not deferred) because it's the only option that scores well on Compatibility and covers device configuration, if stakeholder feedback later asks for a fuller mobile experience, Compatibility and Interaction capability are exactly where the data already says Mobile is strongest.

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