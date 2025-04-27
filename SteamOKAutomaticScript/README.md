## SteamOKAutoScript

### Features
- Automates the installation and testing of games on SteamOK
- Handles license agreements automatically
- Takes screenshots during process for debugging
- Produces Excel reports of game status
- DLL injection for additional game functionality

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

### Usage
```
# Run with default configuration
python main.py

# Run with custom configuration file
python main.py --config path/to/custom/config.yaml

# Run DLL injection only
python main.py --inject