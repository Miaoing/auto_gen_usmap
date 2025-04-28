## SteamOKAutoScript

### Features
- Automates the installation and testing of games on SteamOK
- Handles license agreements automatically
- Takes screenshots during process for debugging
- Produces Excel reports of game status
- DLL injection for additional game functionality
- CSV logging of game status, download errors, injection crashes, and USMap paths
- Organized debug screenshots with separate folders for each game

### Configuration
The application now supports a YAML-based configuration system. The default configuration file is located at `config/config.yaml`. You can:
- Modify the default configuration file
- Specify a custom configuration file with the `--config` command line argument

Configuration options include:
- File paths and directories
- Image recognition confidence levels
- Timing parameters (delays, timeouts)
- DLL injection settings
- OCR settings

#### Debug Screenshots
The application now captures debug screenshots throughout the game installation and injection process:

- Each game gets a separate timestamped folder to organize screenshots
- Screenshots are taken at key points in the process:
  - When starting to process a game
  - After searching for a game
  - When viewing game details
  - When starting installation
  - During download (at specific progress milestones)
  - After installation completes
  - Before and after DLL injection
  
Screenshot captures are intelligently throttled:
- Key moments always get screenshots
- For longer installations, progress screenshots are taken at reasonable intervals (every 20% progress)
- Download progress screenshots are limited (approximately every 10% completion) to avoid filling disk space

Screenshot folders follow this naming pattern:
```
screenshots/GameName_YYYYMMDD_HHMMSS/
```

Individual screenshots include the type and timestamp in their filename:
```
search_results_HHMMSS.png
download_50pct_HHMMSS.png
installation_complete_HHMMSS.png
```

#### DLL Injection Configuration
The DLL injection functionality can be configured with the following settings:

```yaml
dll_injection:
  enabled: true  # Toggle DLL injection functionality
  timeout: 60    # Base timeout for injection
  
  # DLL Injection specific paths
  paths:
    log_directory: "C:/Dumper-7/log"  # Directory for injection logs
  
  # Image paths for DLL injection process
  images:
    playable_image: "png/playable.png"       # Image to identify playable button
    playable_confidence: 0.8                 # Confidence threshold for image match
    start_game_image: "png/start_game.png"   # Game startup button image
    # Additional image configurations...
  
  # Sleep timings for different parts of the injection process
  sleep_timings:
    window_activate: 0.3       # Time after window activation
    click_delay: 0.5           # Time after clicking
    # Additional timing configurations...
    
  # Retry counts for various detection steps
  retry_counts:
    playable_detection: 10     # Max attempts for playable button
    launch_options: 5          # Max attempts for launch options
    # Additional retry configurations...
```

#### USMap File Location
After a successful injection, the system will search for the USMap file in the following locations:

1. First, it checks inside the injection log directory for any `.usmap` files or a `usmap.txt` file containing the path
2. If not found there, it looks in the parent directory structure for timestamp folders created after the injection
3. Within those timestamp folders, it searches for a `Mappings` folder containing `.usmap` files

The typical path for USMap files is:
```
parent_directory/timestamp_folder/Mappings/GameName.usmap
```

For example, if the log directory is `C:/Dumper-7/log/20230615_120000`, the system will check for USMap files in:
```
C:/Dumper-7/20230615_120500/Mappings/*.usmap
```
(where 20230615_120500 is a timestamp folder created after the injection)

#### CSV Logging
The application logs detailed game processing status to a CSV file, including:
- Game name
- Processing status (download success/error, injection success/crash/timeout)
- Timestamp of each operation
- USMap path for successful injections
- Injection log directory for tracking all injection-related operations
- Error details when applicable

The CSV file contains the following columns:
1. **GameName**: Name of the game
2. **Status**: Current status (DOWNLOAD_ERROR, DOWNLOAD_SUCCESS, INJECTION_CRASH, INJECTION_TIMEOUT, INJECTION_SUCCESS)
3. **Timestamp**: When the log entry was created
4. **USMapPath**: Path to the USMap file (for successful injections - located in Mappings folder)
5. **InjectionLogDir**: Directory where injection logs are stored
6. **ErrorDetails**: Details about any errors that occurred

The CSV file is automatically created in the `result` directory with a timestamp in the filename.

To run the test script that demonstrates all different logging scenarios:
```
python test_csv_logger.py
```

### TODO
- [x] Steam点击安装后，有时会出现许可协议，需要点击接受
- [ ] SteamOK有时候会崩，需要时刻检测错误弹窗，然后重启SteamOK
- [x] Steam点击安装和接受后，仍然会出现并未下载的bug，需要重试
- [x] 每一步都截个图并保存
- [x] 结果最好一个游戏放到一个文件夹里
- [x] 可以删除game_results.txt了，把games.xlsx移到result下
- [ ] 下载完毕后根据最新修改时间排序，打包第一个为7z，文件名改为steamid_游戏名空格替换为空格。copy到移动硬盘，删除d盘
- [x] 添加配置文件系统
- [x] 为DLL注入添加完整配置参数
- [x] 添加CSV日志记录游戏状态、下载错误和注入结果
- [x] 完善CSV日志记录注入超时和日志目录信息
- [x] 正确识别并记录USMap文件路径 (在Mappings文件夹中)
- [x] 为每个游戏创建单独的、带时间戳的截图文件夹

### Usage
```
# Run with default configuration
python main.py

# Run with custom configuration file
python main.py --config path/to/custom/config.yaml

# Run with custom CSV log file
python main.py --csv path/to/custom/logfile.csv

# Run DLL injection only
python main.py --inject