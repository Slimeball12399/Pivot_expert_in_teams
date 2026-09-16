# Enginnering Decisions
### Scoring

## Platform
Criterion | Weight | Mobile | Desktop | Web 
--- | --- | --- | --- |--- 
Cross-Platform Accessibility | 20% |  | 
Cost Efficiency | 10% | | 
Functional suitability | 10% | | 
Maintanace & Reliability | 15% | | 
Interaction capability | 20% | |
Compatibility | 15% | | 
Performance efficiency | 5% | | 
Security | 5% | | 
TOTAL | 100% | | 
### Refs
- https://www.3appes.com/web-vs-mobile-vs-desktop/
- https://blog.pacificcert.com/iso-25010-software-product-quality-model/

## Backend server
Criterion | Weight | Django | Laravel | FastAPI | .ASP.NET Core 
--- | --- | --- | --- | --- |--- 
Maintainability | 5% | | |
Team Familiarity | 10% | | |
Function set | 10% | | |
Security | 5% | | |
Flexibility | 10% | | |
Integration | 20% | | | 
Data Processing Capabilities | 15% | | | |
Visualization | 15% | | | |
Performance | 10% | | | |
TOTAL | 100% | | 

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


## Comuncation with the board
What standard do we wanna use for communication
1. **Process on board** - The board sens the data that needs to be visualized out to server or device not much processing outside
2. **Server processes** - Data is sent to the server from the board than sent back to display after analysis
3. **Mobile processes** - The mobile device processes the data only send data to server after analysis
4. **Stream to both** - The device streams to server and mobile at the same time mobile visualizes server does porcessing
5. **Mobile as gateway** - Mobile gets raw data shows non processing data directly than send all to the server for analysis

| Criterion | Weight | 1. Process on board | 2. Server processes | 3. Mobile processes | 4. Stream to both | 5. Mobile as gateway |
|---|---|---|---|---|---|---|
| Performance | 10% | | | | | |
| Latency | 20% | | | | | |
| Ease of implementation | 10% | | | | | |
| User experience | 10% | | | | | |
| Reliability (network dependence) | 15%  | | | | | |
| Hardware requirements (board) | 15% | | | | | |
| Power / battery usage | 20% | | | | | |
| Number of to mobile | 1 | 1 | 2 | 1 | 1-2 | 3
| **Total** | **100%** | | | | | |

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