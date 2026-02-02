import time
import os
import json
import winreg
from datetime import datetime
import re

def get_steam_install_path():
    """Получаем путь установки Steam из реестра Windows"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                           r"Software\Valve\Steam")
        steam_path = winreg.QueryValueEx(key, "SteamPath")[0]
        winreg.CloseKey(key)
        return steam_path
    except Exception as e:
        print(f"Ошибка при чтении реестра: {e}")
        # Попробуем стандартный путь
        default_path = r"C:\Program Files (x86)\Steam"
        if os.path.exists(default_path):
            return default_path
        return None

def get_downloading_game_name(steam_path):
    """Получаем название загружаемой игры из логов"""
    logs_dir = os.path.join(steam_path, "logs")
    
    if not os.path.exists(logs_dir):
        return "Неизвестная игра"
    
    # Ищем последний лог-файл
    log_files = [f for f in os.listdir(logs_dir) 
                if f.startswith("content_log") and f.endswith(".txt")]
    
    if not log_files:
        return "Неизвестная игра"
    
    # Берем самый свежий лог
    latest_log = max(log_files)
    log_path = os.path.join(logs_dir, latest_log)
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        # Ищем строки с информацией о загрузке
        for line in reversed(lines[-100:]):  # Проверяем последние 100 строк
            if '"appid"' in line and '"name"' in line:
                try:
                    # Пробуем извлечь JSON
                    json_start = line.find('{')
                    if json_start != -1:
                        data = json.loads(line[json_start:])
                        if 'name' in data:
                            return data['name']
                except:
                    pass
                    
            # Альтернативный способ - поиск по шаблону
            match = re.search(r'Downloading app (\d+)\s+(.+?)(?:\n|$)', line)
            if match:
                return match.group(2).strip()
                
    except Exception as e:
        print(f"Ошибка при чтении лога: {e}")
    
    return "Неизвестная игра"

def get_download_status(steam_path):
    """Получаем статус загрузки из логов"""
    logs_dir = os.path.join(steam_path, "logs")
    
    if not os.path.exists(logs_dir):
        return "пауза", 0
    
    # Проверяем файл downloading_stats.txt (если есть)
    stats_file = os.path.join(steam_path, "config", "downloading_stats.txt")
    if os.path.exists(stats_file):
        try:
            with open(stats_file, 'r') as f:
                stats = f.read()
                if "paused" in stats.lower():
                    return "пауза", 0
        except:
            pass
    
    # Проверяем лог загрузок
    content_log = os.path.join(logs_dir, "content_log.txt")
    if os.path.exists(content_log):
        try:
            with open(content_log, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if "paused" in content.lower() or "suspend" in content.lower():
                    return "пауза", 0
        except:
            pass
    
    # Проверяем наличие активных загрузок через библиотеки
    library_folders_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    if os.path.exists(library_folders_path):
        try:
            with open(library_folders_path, 'r') as f:
                content = f.read()
                # Если есть активные загрузки, будут упоминания о downloading
                if '"downloading"' in content and '"1"' in content:
                    # Пробуем извлечь скорость
                    speed_match = re.search(r'"bytespersecond"\s+"(\d+)"', content)
                    if speed_match:
                        speed_bytes = int(speed_match.group(1))
                        return "активно", speed_bytes
                    return "активно", 0
        except:
            pass
    
    return "неактивно", 0

def format_speed(bytes_per_second):
    """Форматируем скорость в читаемый вид"""
    if bytes_per_second == 0:
        return "0 B/s"
    
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.2f} {unit}"
        bytes_per_second /= 1024
    return f"{bytes_per_second:.2f} TB/s"

def monitor_steam_downloads():
    """Основная функция мониторинга"""
    print("=== Мониторинг загрузок Steam ===")
    print("Скрипт запущен. Начинаем мониторинг...\n")
    
    steam_path = get_steam_install_path()
    
    if not steam_path:
        print("Ошибка: Steam не найден!")
        return
    
    print(f"Путь к Steam: {steam_path}")
    
    # Мониторим в течение 5 минут с интервалом 1 минута
    for minute in range(5):
        current_time = datetime.now().strftime("%H:%M:%S")
        game_name = get_downloading_game_name(steam_path)
        status, speed_bytes = get_download_status(steam_path)
        
        print(f"\n[{current_time}] Минута {minute + 1}/5")
        print(f"Игра: {game_name}")
        print(f"Статус: {status}")
        
        if status == "активно" and speed_bytes > 0:
            speed_formatted = format_speed(speed_bytes)
            print(f"Скорость загрузки: {speed_formatted}")
        elif status == "пауза":
            print("Загрузка на паузе")
        else:
            print("Нет активных загрузок")
        
        if minute < 4:  # Не ждать после последней итерации
            time.sleep(60)  # Ждем 1 минуту
    
    print("\n=== Мониторинг завершен ===")

def run_in_background():
    """Запуск в фоновом режиме"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--background":
        # В фоновом режиме
        while True:
            monitor_steam_downloads()
            print("\nПерезапуск мониторинга через 5 минут...")
            time.sleep(300)  # Пауза 5 минут перед перезапуском
    else:
        # Обычный запуск на 5 минут
        monitor_steam_downloads()

if __name__ == "__main__":
    # Для запуска в фоне используйте: python steam_monitor.py --background
    # Для однократного запуска: python steam_monitor.py
    run_in_background()
