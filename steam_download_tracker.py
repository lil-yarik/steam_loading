import os
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import re
import threading

# Для Windows - работа с реестром
try:
    import winreg
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False
    # Для Linux/Mac
    import subprocess

class SteamDownloadTracker:
    def __init__(self, check_interval: int = 60, total_duration: int = 300):
        """
        Инициализация трекера
        
        Args:
            check_interval: интервал проверки в секундах (по умолчанию 60)
            total_duration: общая продолжительность мониторинга в секундах (по умолчанию 300 = 5 минут)
        """
        self.check_interval = check_interval
        self.total_duration = total_duration
        self.steam_path = None
        self.current_game = None
        self.last_bytes = 0
        self.last_check_time = None
        
        # Настройка логирования
        self.setup_logging()
        
    def setup_logging(self):
        """Настройка системы логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.StreamHandler(),  # Вывод в консоль
                logging.FileHandler('steam_tracker.log', encoding='utf-8')  # Лог-файл
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def find_steam_path(self) -> Optional[str]:
        """Поиск пути установки Steam"""
        try:
            if IS_WINDOWS:
                # Поиск в реестре Windows
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                      r"Software\Valve\Steam") as key:
                        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                        self.logger.info(f"Steam найден в реестре: {steam_path}")
                        return steam_path
                except WindowsError:
                    # Попробуем стандартные пути
                    common_paths = [
                        r"C:\Program Files (x86)\Steam",
                        r"C:\Program Files\Steam",
                        os.path.expanduser(r"~\Steam")
                    ]
                    for path in common_paths:
                        if os.path.exists(path):
                            self.logger.info(f"Steam найден в стандартном пути: {path}")
                            return path
            else:
                # Для Linux
                home = os.path.expanduser("~")
                linux_paths = [
                    f"{home}/.steam/steam",
                    f"{home}/.local/share/Steam",
                    "/usr/share/steam"
                ]
                for path in linux_paths:
                    if os.path.exists(path):
                        self.logger.info(f"Steam найден: {path}")
                        return path
                
                # Для MacOS
                mac_paths = [
                    f"{home}/Library/Application Support/Steam",
                    "/Applications/Steam.app"
                ]
                for path in mac_paths:
                    if os.path.exists(path):
                        self.logger.info(f"Steam найден: {path}")
                        return path
            
            self.logger.warning("Steam не найден в стандартных расположениях")
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка при поиске Steam: {e}")
            return None
    
    def get_download_info(self) -> Dict[str, Any]:
        """
        Получение информации о текущих загрузках Steam
        
        Returns:
            Словарь с информацией о загрузке
        """
        try:
            if not self.steam_path:
                return {"status": "steam_not_found"}
            
            # Путь к файлам конфигурации Steam
            config_dir = os.path.join(self.steam_path, "config")
            if not os.path.exists(config_dir):
                return {"status": "no_config"}
            
            # Чтение файла библиотеки (может содержать информацию о загрузках)
            library_vdf = os.path.join(config_dir, "libraryfolders.vdf")
            if os.path.exists(library_vdf):
                with open(library_vdf, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    # Поиск информации о загрузках в файле
                    # Это упрощенный парсинг, в реальности нужно более сложное
                    if '"downloading"' in content.lower():
                        return {"status": "downloading", "game": "Unknown Game"}
            
            # Альтернативный метод: проверка директории downloads
            downloads_dir = os.path.join(self.steam_path, "steamapps", "downloading")
            if os.path.exists(downloads_dir):
                games = os.listdir(downloads_dir)
                if games:
                    # Получение имени игры по AppID
                    game_name = self.get_game_name(games[0])
                    return {
                        "status": "downloading",
                        "game": game_name,
                        "app_id": games[0]
                    }
            
            return {"status": "no_downloads"}
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении информации о загрузках: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_game_name(self, app_id: str) -> str:
        """Получение имени игры по AppID"""
        try:
            # Попытка получить имя из локального кеша
            appcache_dir = os.path.join(self.steam_path, "appcache")
            if os.path.exists(appcache_dir):
                # Проверка различных файлов кеша
                cache_files = ["appinfo.vdf", "librarycache"]
                for file in cache_files:
                    cache_path = os.path.join(appcache_dir, file)
                    if os.path.exists(cache_path):
                        # В реальном приложении здесь был бы парсинг VDF
                        # Для простоты возвращаем AppID
                        return f"Игра (AppID: {app_id})"
            
            # Если не нашли в кеше, используем статический словарь популярных игр
            popular_games = {
                "730": "Counter-Strike 2",
                "570": "Dota 2",
                "578080": "PUBG: BATTLEGROUNDS",
                "1091500": "Cyberpunk 2077",
                "1172470": "Apex Legends",
                "271590": "Grand Theft Auto V",
                "1245620": "ELDEN RING",
                "292030": "The Witcher 3: Wild Hunt",
                "1085660": "Destiny 2",
                "381210": "Dead by Daylight"
            }
            
            return popular_games.get(app_id, f"Неизвестная игра (AppID: {app_id})")
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении имени игры: {e}")
            return f"Игра (AppID: {app_id})"
    
    def calculate_speed(self, current_bytes: int) -> float:
        """Расчет скорости загрузки"""
        if self.last_bytes == 0 or not self.last_check_time:
            self.last_bytes = current_bytes
            self.last_check_time = time.time()
            return 0.0
        
        current_time = time.time()
        time_diff = current_time - self.last_check_time
        bytes_diff = current_bytes - self.last_bytes
        
        if time_diff > 0:
            speed_bps = bytes_diff / time_diff
            speed_mbps = speed_bps / 1_048_576  # Конвертация в MB/s
        else:
            speed_mbps = 0.0
        
        # Обновление последних значений
        self.last_bytes = current_bytes
        self.last_check_time = current_time
        
        return speed_mbps
    
    def get_network_stats(self) -> Dict[str, Any]:
        """Получение сетевой статистики (симуляция для примера)"""
        try:
            # В реальном приложении здесь был бы мониторинг сетевого трафика
            # или парсинг логов Steam. Для примера используем симуляцию.
            
            import random
            import psutil
            
            # Получение реальной сетевой статистики через psutil
            net_io = psutil.net_io_counters()
            current_bytes = net_io.bytes_recv
            
            # Расчет скорости
            speed_mbps = self.calculate_speed(current_bytes)
            
            # Случайное определение статуса для демонстрации
            statuses = ["downloading", "paused", "completed"]
            status = random.choice(statuses)
            
            return {
                "speed_mbps": round(speed_mbps, 2),
                "total_bytes": current_bytes,
                "status": status
            }
            
        except ImportError:
            # Если psutil не установлен, используем симуляцию
            self.logger.warning("psutil не установлен, используется симуляция данных")
            
            # Имитация сетевой активности
            current_bytes = self.last_bytes + int(50_000_000 * (self.check_interval / 60))
            speed_mbps = self.calculate_speed(current_bytes)
            
            # Чередование статусов для демонстрации
            status_cycle = ["downloading", "downloading", "downloading", "paused", "completed"]
            status_index = int(time.time() / self.check_interval) % len(status_cycle)
            
            return {
                "speed_mbps": round(speed_mbps, 2),
                "total_bytes": current_bytes,
                "status": status_cycle[status_index]
            }
        except Exception as e:
            self.logger.error(f"Ошибка при получении сетевой статистики: {e}")
            return {"speed_mbps": 0.0, "total_bytes": 0, "status": "error"}
    
    def monitor_downloads(self):
        """Основной цикл мониторинга загрузок"""
        self.logger.info("=" * 50)
        self.logger.info("Запуск мониторинга загрузок Steam")
        self.logger.info(f"Интервал проверки: {self.check_interval} сек")
        self.logger.info(f"Общая продолжительность: {self.total_duration} сек")
        self.logger.info("=" * 50)
        
        # Поиск Steam
        self.steam_path = self.find_steam_path()
        if not self.steam_path:
            self.logger.error("Steam не найден! Убедитесь, что Steam установлен.")
            return
        
        start_time = time.time()
        check_count = 0
        max_checks = self.total_duration // self.check_interval
        
        while check_count < max_checks:
            try:
                check_count += 1
                current_time = time.time()
                elapsed = current_time - start_time
                
                self.logger.info(f"\nПроверка #{check_count} (прошло {int(elapsed)} сек)")
                
                # Получение информации о загрузке
                download_info = self.get_download_info()
                network_stats = self.get_network_stats()
                
                # Объединение информации
                info = {**download_info, **network_stats}
                
                # Вывод информации
                if info.get("status") == "downloading":
                    game_name = info.get("game", "Неизвестная игра")
                    speed = info.get("speed_mbps", 0)
                    status_text = "Скачивается"
                    
                    self.logger.info(f"🎮 Игра: {game_name}")
                    self.logger.info(f"📊 Статус: {status_text}")
                    self.logger.info(f"🚀 Скорость: {speed} MB/s")
                    
                elif info.get("status") == "paused":
                    self.logger.info("⏸️ Загрузка на паузе")
                    
                elif info.get("status") == "completed":
                    self.logger.info("✅ Загрузка завершена")
                    
                elif info.get("status") == "no_downloads":
                    self.logger.info("📭 Нет активных загрузок")
                    
                else:
                    self.logger.warning(f"Неизвестный статус: {info.get('status')}")
                
                # Ожидание следующей проверки
                if check_count < max_checks:
                    self.logger.info(f"⏳ Следующая проверка через {self.check_interval} сек...")
                    time.sleep(self.check_interval)
                    
            except KeyboardInterrupt:
                self.logger.info("\n⏹️ Мониторинг прерван пользователем")
                break
            except Exception as e:
                self.logger.error(f"Ошибка в цикле мониторинга: {e}")
                time.sleep(self.check_interval)
        
        self.logger.info("=" * 50)
        self.logger.info("Мониторинг завершен!")
        self.logger.info(f"Выполнено проверок: {check_count}")
        self.logger.info(f"Общее время: {int(time.time() - start_time)} сек")
        self.logger.info("=" * 50)
    
    def run_background(self):
        """Запуск мониторинга в фоновом режиме"""
        self.logger.info("🚀 Запуск в фоновом режиме...")
        
        # Создание потока для мониторинга
        monitor_thread = threading.Thread(target=self.monitor_downloads, daemon=True)
        monitor_thread.start()
        
        try:
            # Ожидание завершения потока
            while monitor_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("\nЗавершение работы...")
            sys.exit(0)

def main():
    """Основная функция"""
    print("=" * 60)
    print("Steam Download Tracker v1.0")
    print("Скрипт для отслеживания скорости загрузки игр в Steam")
    print("=" * 60)
    
    try:
        # Создание и запуск трекера
        tracker = SteamDownloadTracker(
            check_interval=60,  # Проверка каждую минуту
            total_duration=300   # Всего 5 минут
        )
        
        # Запрос режима работы
        print("\nВыберите режим работы:")
        print("1. Обычный режим (вывод в консоль)")
        print("2. Фоновый режим")
        print("3. Настроить параметры")
        
        choice = input("\nВаш выбор (1-3): ").strip()
        
        if choice == "2":
            tracker.run_background()
        elif choice == "3":
            # Настройка параметров
            try:
                interval = int(input("Интервал проверки в секундах (по умолчанию 60): ") or "60")
                duration = int(input("Общая продолжительность в секундах (по умолчанию 300): ") or "300")
                tracker = SteamDownloadTracker(check_interval=interval, total_duration=duration)
                tracker.monitor_downloads()
            except ValueError:
                print("Ошибка! Введите числовые значения.")
                return
        else:
            tracker.monitor_downloads()
            
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        logging.error(f"Критическая ошибка: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    # Проверка зависимостей
    try:
        import psutil
    except ImportError:
        print("⚠️  Внимание: библиотека psutil не установлена")
        print("Установите её для более точного отслеживания: pip install psutil")
        print("Будет использована симуляция данных.\n")
    
    sys.exit(main())
