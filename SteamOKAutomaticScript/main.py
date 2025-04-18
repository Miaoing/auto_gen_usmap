import time
import logging
import pandas as pd
import argparse
from logger import setup_logging
from game_install_controller import SteamOKController
from ocr_helper import OcrHelper
from dll_inject import DLLInjector

logger = setup_logging()


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='SteamOK Automatic Script')
    parser.add_argument('--inject', action='store_true', help='Run the DLL injection process')
    args = parser.parse_args()
    
    # If injection mode is selected, run the injector and exit
    if args.inject:
        logger.info("Running in DLL injection mode...")
        injector = DLLInjector()
        result = injector.run_injection_process()
        print(f"DLL injection {'successful' if result else 'failed'}")
        return
    
    # Otherwise, run the normal game installation process
    try:
        logger.info("脚本启动中...")
        OcrHelper.initialize()

        controller = SteamOKController()
        injector = DLLInjector(r'F:\steam\steamapps\common')  # Initialize the DLL injector
        
        try:
            df = pd.read_excel('result/games.xlsx')
            start_index = df.index[df.iloc[:, 2].isna()].tolist()[0] if any(df.iloc[:, 2].isna()) else 0
            games = df.iloc[start_index:, 1].tolist()
            logger.info(f"从第{start_index + 1}行开始加载{len(games)}个游戏")
        except Exception as e:
            logger.error(f"从Excel加载游戏列表时出错: {e}")
            games = []

        for game in games:
            try:
                # Process the game (download and check if playable)
                result = controller.process_game(game)
                
                # Initialize inject_result to False by default
                inject_result = False
                
                # If the game is successfully processed (downloaded and playable), run DLL injection
                if result:
                    logger.info(f"Game {game} is playable, starting DLL injection process...")
                    inject_result = injector.run_injection_process()
                    if inject_result:
                        logger.info(f"DLL injection successful for game: {game}")
                    else:
                        logger.error(f"DLL injection failed for game: {game}")
                
                print(f"{game}: {'可玩' if result else '不可玩'}, {'已注入DLL' if result and inject_result else '未注入DLL'}")
                time.sleep(2)
            except Exception as e:
                logger.error(f"处理游戏{game}时出错: {e}")
                print(f"处理游戏{game}时出错")
                continue

        print("处理完成。结果已保存")
    except Exception as e:
        logger.error(f"应用程序错误: {e}")
        print(f"错误: {e}")
    finally:
        logger.info("脚本结束")


if __name__ == "__main__":
    main()
