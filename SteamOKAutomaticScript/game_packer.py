import os
import subprocess
import time
import logging
import pandas as pd
from game_install_controller import SteamOKController

logger = logging.getLogger()

class GamePacker:
    def __init__(self):
        self.steam_common_path = "F:\\steam\\steamapps\\common"
        self.controller = SteamOKController()

    def get_latest_game_folder(self):
        """获取最新修改的游戏文件夹"""
        try:
            # 获取所有文件夹并按修改时间排序
            folders = [
                f for f in os.listdir(self.steam_common_path)
                if os.path.isdir(os.path.join(self.steam_common_path, f))
            ]
            if not folders:
                logger.error("No game folders found")
                return None

            folders.sort(
                key=lambda x: os.path.getmtime(os.path.join(self.steam_common_path, x)),
                reverse=True
            )
            return folders[0]
        except Exception as e:
            logger.error(f"Error getting latest game folder: {e}")
            return None

    def get_game_steamid(self, game_folder):
        """从Excel文件中获取游戏对应的steamid"""
        try:
            df = pd.read_excel('result/games.xlsx')
            # 在第一列（steamid列）中查找游戏名称对应的steamid
            game_row = df[df.iloc[:, 1] == game_folder]
            if not game_row.empty:
                return str(game_row.iloc[0, 0])
            return None
        except Exception as e:
            logger.error(f"Error getting game steamid: {e}")
            return None

    def pack_game(self, game_folder, steamid):
        """使用7zip打包游戏文件夹"""
        try:
            # 格式化游戏名称
            formatted_name = self.controller._format_game_name(game_folder)
            # 构建打包文件名：实际steamid_格式化游戏名
            archive_name = f"{steamid}_{formatted_name}"
            source_path = os.path.join(self.steam_common_path, game_folder)
            output_path = os.path.join(self.steam_common_path, f"{archive_name}.zip")

            # 构建7z命令，使用完整路径
            seven_zip_path = "C:\\Program Files\\7-Zip\\7z.exe"
            cmd = [
                seven_zip_path,
                "a",  # 添加到压缩包
                "-tzip",  # 使用zip格式
                "-mx0",  # 不压缩，仅打包
                output_path,
                source_path
            ]

            # 执行7zip命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"Successfully packed game: {game_folder}")
                
                # 创建E盘目标目录
                target_dir = "E:\\SteamGames"
                os.makedirs(target_dir, exist_ok=True)
                
                # 复制文件到E盘，然后删除源文件
                target_path = os.path.join(target_dir, f"{archive_name}.zip")
                import shutil
                shutil.copy2(output_path, target_path)
                os.remove(output_path)
                logger.info(f"Successfully copied packed game to: {target_path}")
                
                # 删除原始游戏文件夹
                shutil.rmtree(source_path)
                logger.info(f"Successfully deleted original game folder: {source_path}")
                
                return True
            else:
                logger.error(f"Failed to pack game: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error packing game: {e}")
            return False

    def process_latest_game(self, original_game_name):
        """处理最新的游戏文件夹"""
        # 先获取steamid
        steamid = self.get_game_steamid(original_game_name)
        if not steamid:
            logger.error(f"Could not find steamid for game: {original_game_name}")
            return False

        # 获取最新修改的游戏文件夹
        game_folder = self.get_latest_game_folder()
        if game_folder:
            logger.info(f"Found latest game folder: {game_folder}")
            if self.pack_game(game_folder, steamid):
                logger.info("Game packing completed successfully")
                return True
        return False

def main():
    packer = GamePacker()
    packer.process_latest_game("")

if __name__ == "__main__":
    main()