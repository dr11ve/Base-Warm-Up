import os
import random
import requests
import time
import tkinter as tk
from tkinter import ttk, messagebox
from mnemonic import Mnemonic
from web3 import Web3, Account
from concurrent.futures import ThreadPoolExecutor, as_completed
from eth_abi import encode

FILES = {"proxy": "proxies.txt", "seed": "seeds.txt", "private": "private_keys.txt", "settings": "settings.txt"}

# Base Network Configuration
RPC_URL = "https://mainnet.base.org"
BASE_CHAIN_ID = 8453
NATIVE_TOKEN = "ETH"
EXPLORER_URL = "https://basescan.org"

# Token addresses on Base
USDC_TOKEN = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH_TOKEN = "0x4200000000000000000000000000000000000006"

# Protocol Contract Addresses (will need to be verified from actual transactions)
# Bungee uses the same Uniswap V2 router as PancakeSwap on Base
BUNGEE_ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481"  # Uniswap V2 Router on Base (same as PancakeSwap)
PANCAKE_ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481"
UNISWAP_ROUTER = "0x2626664c2603336E57B271c5C0b26F421741e481"
PENDLE_ROUTER = "0x0000000001E4ef00d069e71d6bA041b0A16F7eA0"
COMPOUND_COMPTROLLER = "0xb21b06D71c7598698be62296A3482b9Ba3EB35d5"
COMPOUND_CE_ETH = "0x1B0e765F6224C21223AeA2af16c1C46E38885a40"
AAVE_POOL = "0xA238Dd80C259a72e81d7e466Fa5217c4f9F8F7C9"
MOONWELL_COMPTROLLER = "0xfBb21d0380beE3312B33c4353c8936a0F13EF26C"

# Common ABIs
ERC20_ABI = [
    {"inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "owner", "type": "address"}, {"internalType": "address", "name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"}
]

UNISWAP_V2_ROUTER_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "amountOutMin", "type": "uint256"}, {"internalType": "address[]", "name": "path", "type": "address[]"}, {"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "deadline", "type": "uint256"}], "name": "swapExactETHForTokens", "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}], "stateMutability": "payable", "type": "function"},
    {"inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"}, {"internalType": "address[]", "name": "path", "type": "address[]"}], "name": "getAmountsOut", "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}], "stateMutability": "view", "type": "function"}
]

UNISWAP_V3_ROUTER_ABI = [
    {"inputs": [
        {"components": [
            {"internalType": "address", "name": "tokenIn", "type": "address"},
            {"internalType": "address", "name": "tokenOut", "type": "address"},
            {"internalType": "uint24", "name": "fee", "type": "uint24"},
            {"internalType": "address", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMinimum", "type": "uint256"},
            {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
        ], "internalType": "struct ISwapRouter.ExactInputSingleParams", "name": "params", "type": "tuple"}
    ], "name": "exactInputSingle", "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}], "stateMutability": "payable", "type": "function"}
]

UNISWAP_V3_QUOTER_ABI = [
    {"inputs": [
        {"internalType": "address", "name": "tokenIn", "type": "address"},
        {"internalType": "address", "name": "tokenOut", "type": "address"},
        {"internalType": "uint24", "name": "fee", "type": "uint24"},
        {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
        {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
    ], "name": "quoteExactInputSingle", "outputs": [
        {"internalType": "uint256", "name": "amountOut", "type": "uint256"}
    ], "stateMutability": "nonpayable", "type": "function"}
]

# Uniswap V3 Quoter контракт на Base
UNISWAP_V3_QUOTER = "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a"

# Socket/Bungee ABI - использует swap через Socket
SOCKET_ROUTER_ABI = [
    {"inputs": [
        {"internalType": "uint32", "name": "routeId", "type": "uint32"},
        {"internalType": "bytes", "name": "data", "type": "bytes"}
    ], "name": "swap", "outputs": [], "stateMutability": "payable", "type": "function"},
    {"inputs": [
        {"internalType": "address", "name": "tokenIn", "type": "address"},
        {"internalType": "address", "name": "tokenOut", "type": "address"},
        {"internalType": "uint256", "name": "amountIn", "type": "uint256"}
    ], "name": "getAmountOut", "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}], "stateMutability": "view", "type": "function"}
]

PENDLE_ROUTER_ABI = [
    {"inputs": [
        {"internalType": "address", "name": "receiverYT", "type": "address"},
        {"internalType": "address", "name": "receiverPT", "type": "address"},
        {"internalType": "address", "name": "market", "type": "address"},
        {"internalType": "uint256", "name": "exactSyIn", "type": "uint256"},
        {"internalType": "uint256", "name": "minYTOut", "type": "uint256"},
        {"internalType": "uint256", "name": "minPTOut", "type": "uint256"}
    ], "name": "swapExactSyForYt", "outputs": [
        {"internalType": "uint256", "name": "netYtOut", "type": "uint256"},
        {"internalType": "uint256", "name": "netSyFee", "type": "uint256"}
    ], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [
        {"internalType": "address", "name": "receiverYT", "type": "address"},
        {"internalType": "address", "name": "receiverPT", "type": "address"},
        {"internalType": "address", "name": "market", "type": "address"},
        {"internalType": "uint256", "name": "exactSyIn", "type": "uint256"},
        {"internalType": "uint256", "name": "minYTOut", "type": "uint256"},
        {"internalType": "uint256", "name": "minPTOut", "type": "uint256"}
    ], "name": "swapExactSyForPt", "outputs": [
        {"internalType": "uint256", "name": "netPtOut", "type": "uint256"},
        {"internalType": "uint256", "name": "netSyFee", "type": "uint256"}
    ], "stateMutability": "nonpayable", "type": "function"}
]

COMPOUND_ABI = [
    {"inputs": [{"internalType": "address", "name": "cToken", "type": "address"}], "name": "mint", "outputs": [], "stateMutability": "payable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "cToken", "type": "address"}, {"internalType": "uint256", "name": "mintAmount", "type": "uint256"}], "name": "mint", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

BEEFY_VAULT_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "_amount", "type": "uint256"}], "name": "deposit", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "depositAll", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]

AAVE_POOL_ABI = [
    {"inputs": [
        {"internalType": "address", "name": "asset", "type": "address"},
        {"internalType": "uint256", "name": "amount", "type": "uint256"},
        {"internalType": "address", "name": "onBehalfOf", "type": "address"},
        {"internalType": "uint16", "name": "referralCode", "type": "uint16"}
    ], "name": "supply", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [
        {"internalType": "address", "name": "asset", "type": "address"},
        {"internalType": "uint256", "name": "amount", "type": "uint256"},
        {"internalType": "address", "name": "onBehalfOf", "type": "address"},
        {"internalType": "uint16", "name": "referralCode", "type": "uint16"}
    ], "name": "supply", "outputs": [], "stateMutability": "payable", "type": "function"}
]

MOONWELL_COMPTROLLER_ABI = [
    {"inputs": [
        {"internalType": "address", "name": "mToken", "type": "address"},
        {"internalType": "uint256", "name": "mintAmount", "type": "uint256"}
    ], "name": "mint", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [
        {"internalType": "address", "name": "mToken", "type": "address"}
    ], "name": "mint", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "payable", "type": "function"}
]

def create_files():
    """Создает все необходимые файлы с шаблонами и инструкцией при первом запуске"""
    files_created = []
    
    if not os.path.exists(FILES["seed"]):
        with open(FILES["seed"], "w", encoding="utf-8") as f:
            f.write("# Seed-фразы (мнемонические фразы) кошельков\n")
            f.write("# Каждая фраза на новой строке (12 слов через пробел)\n")
            f.write("# Пример:\n")
            f.write("# word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12\n")
        files_created.append(FILES["seed"])
    
    if not os.path.exists(FILES["private"]):
        with open(FILES["private"], "w", encoding="utf-8") as f:
            f.write("# Приватные ключи кошельков\n")
            f.write("# Каждый ключ на новой строке (начинается с 0x)\n")
            f.write("# Пример:\n")
            f.write("# 0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef\n")
        files_created.append(FILES["private"])
    
    if not os.path.exists(FILES["proxy"]):
        with open(FILES["proxy"], "w", encoding="utf-8") as f:
            f.write("# Прокси-серверы (опционально)\n")
            f.write("# Каждый прокси на новой строке\n")
            f.write("# Поддерживаемые форматы:\n")
            f.write("# http://username:password@ip:port\n")
            f.write("# http://ip:port\n")
            f.write("# socks5://username:password@ip:port\n")
            f.write("# ip:port:username:password  (автоматически преобразуется)\n")
            f.write("# ip:port  (автоматически преобразуется)\n")
        files_created.append(FILES["proxy"])
    
    if files_created:
        print("\n" + "=" * 60)
        print("📁 СОЗДАНЫ ФАЙЛЫ ПРИ ПЕРВОМ ЗАПУСКЕ")
        print("=" * 60)
        for filename in files_created:
            print(f"✅ {filename}")
        print("=" * 60 + "\n")

def load_from_file(filename):
    """Загружает данные из файла, игнорируя комментарии и пустые строки"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = []
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    lines.append(line)
            return lines
    except:
        return []

def normalize_proxy(proxy_str):
    """Нормализует формат прокси в стандартный URL формат"""
    if not proxy_str or proxy_str == "None":
        return None
    
    proxy_str = proxy_str.strip()
    
    if proxy_str.startswith(('http://', 'https://', 'socks5://', 'socks4://')):
        return proxy_str
    
    parts = proxy_str.split(':')
    
    if len(parts) == 4:
        ip, port, username, password = parts
        return f"http://{username}:{password}@{ip}:{port}"
    elif len(parts) == 2:
        ip, port = parts
        return f"http://{ip}:{port}"
    else:
        return proxy_str

def load_settings():
    """Загружает настройки из файла settings.txt"""
    settings = {
        "bungee_eth_min": 0.0,
        "bungee_eth_max": 0.0,
        "use_random_bungee": False,
        "pancake_eth_min": 0.0,
        "pancake_eth_max": 0.0,
        "use_random_pancake": False,
        "uniswap_eth_min": 0.0,
        "uniswap_eth_max": 0.0,
        "use_random_uniswap": False,
        "pendle_eth_min": 0.0,
        "pendle_eth_max": 0.0,
        "use_random_pendle": False,
        "compound_eth_min": 0.0,
        "compound_eth_max": 0.0,
        "use_random_compound": False,
        "beefy_eth_min": 0.0,
        "beefy_eth_max": 0.0,
        "use_random_beefy": False,
        "aave_eth_min": 0.0,
        "aave_eth_max": 0.0,
        "use_random_aave": False,
        "moonwell_eth_min": 0.0,
        "moonwell_eth_max": 0.0,
        "use_random_moonwell": False,
        "delay_min": 1.0,
        "delay_max": 3.0,
        "max_retry_attempts": 3,
    }
    try:
        with open(FILES["settings"], "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key in settings:
                        if isinstance(settings[key], bool):
                            settings[key] = value.lower() in ("true", "1", "yes", "on")
                        else:
                            settings[key] = float(value)
    except:
        pass
    return settings

def save_settings(settings):
    """Сохраняет настройки в файл settings.txt"""
    try:
        with open(FILES["settings"], "w") as f:
            f.write("# Настройки для модулей\n\n")
            f.write("# Bungee - проценты от баланса ETH (0-100%)\n")
            f.write(f"bungee_eth_min={settings.get('bungee_eth_min', 0.0)}\n")
            f.write(f"bungee_eth_max={settings.get('bungee_eth_max', 0.0)}\n")
            f.write(f"use_random_bungee={settings.get('use_random_bungee', False)}\n\n")
            f.write("# Pancake - проценты от баланса ETH (0-100%)\n")
            f.write(f"pancake_eth_min={settings.get('pancake_eth_min', 0.0)}\n")
            f.write(f"pancake_eth_max={settings.get('pancake_eth_max', 0.0)}\n")
            f.write(f"use_random_pancake={settings.get('use_random_pancake', False)}\n\n")
            f.write("# Uniswap - проценты от баланса ETH (0-100%)\n")
            f.write(f"uniswap_eth_min={settings.get('uniswap_eth_min', 0.0)}\n")
            f.write(f"uniswap_eth_max={settings.get('uniswap_eth_max', 0.0)}\n")
            f.write(f"use_random_uniswap={settings.get('use_random_uniswap', False)}\n\n")
            f.write("# Pendle - проценты от баланса ETH (0-100%)\n")
            f.write(f"pendle_eth_min={settings.get('pendle_eth_min', 0.0)}\n")
            f.write(f"pendle_eth_max={settings.get('pendle_eth_max', 0.0)}\n")
            f.write(f"use_random_pendle={settings.get('use_random_pendle', False)}\n\n")
            f.write("# Compound - проценты от баланса ETH (0-100%)\n")
            f.write(f"compound_eth_min={settings.get('compound_eth_min', 0.0)}\n")
            f.write(f"compound_eth_max={settings.get('compound_eth_max', 0.0)}\n")
            f.write(f"use_random_compound={settings.get('use_random_compound', False)}\n\n")
            f.write("# Beefy - проценты от баланса ETH (0-100%)\n")
            f.write(f"beefy_eth_min={settings.get('beefy_eth_min', 0.0)}\n")
            f.write(f"beefy_eth_max={settings.get('beefy_eth_max', 0.0)}\n")
            f.write(f"use_random_beefy={settings.get('use_random_beefy', False)}\n\n")
            f.write("# AAVE - проценты от баланса ETH (0-100%)\n")
            f.write(f"aave_eth_min={settings.get('aave_eth_min', 0.0)}\n")
            f.write(f"aave_eth_max={settings.get('aave_eth_max', 0.0)}\n")
            f.write(f"use_random_aave={settings.get('use_random_aave', False)}\n\n")
            f.write("# MoonWell - проценты от баланса ETH (0-100%)\n")
            f.write(f"moonwell_eth_min={settings.get('moonwell_eth_min', 0.0)}\n")
            f.write(f"moonwell_eth_max={settings.get('moonwell_eth_max', 0.0)}\n")
            f.write(f"use_random_moonwell={settings.get('use_random_moonwell', False)}\n\n")
            f.write("# Автоматический режим - задержка между операциями (секунды)\n")
            f.write(f"delay_min={settings.get('delay_min', 1.0)}\n")
            f.write(f"delay_max={settings.get('delay_max', 3.0)}\n\n")
            f.write("# Количество попыток для повторного выполнения неудачных транзакций (0 = без ограничений)\n")
            f.write(f"max_retry_attempts={settings.get('max_retry_attempts', 3)}\n")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения настроек: {e}")
        return False

def settings_menu():
    """Открывает GUI окно настроек"""
    root = tk.Tk()
    root.title("⚙️ Настройки модулей")
    root.geometry("650x800")
    
    settings = load_settings()
    
    vars_dict = {}
    modules = [
        ('bungee', 'Bungee', 'bungee_eth_min', 'bungee_eth_max', 'use_random_bungee'),
        ('pancake', 'PancakeSwap', 'pancake_eth_min', 'pancake_eth_max', 'use_random_pancake'),
        ('uniswap', 'Uniswap', 'uniswap_eth_min', 'uniswap_eth_max', 'use_random_uniswap'),
        ('pendle', 'Pendle', 'pendle_eth_min', 'pendle_eth_max', 'use_random_pendle'),
        ('compound', 'Compound', 'compound_eth_min', 'compound_eth_max', 'use_random_compound'),
        ('beefy', 'Beefy', 'beefy_eth_min', 'beefy_eth_max', 'use_random_beefy'),
        ('aave', 'AAVE', 'aave_eth_min', 'aave_eth_max', 'use_random_aave'),
        ('moonwell', 'MoonWell', 'moonwell_eth_min', 'moonwell_eth_max', 'use_random_moonwell'),
    ]
    
    for module_id, module_name, min_key, max_key, random_key in modules:
        vars_dict[module_id] = {
            'min': tk.StringVar(value=str(settings.get(min_key, 0.0))),
            'max': tk.StringVar(value=str(settings.get(max_key, 0.0))),
            'random': tk.BooleanVar(value=settings.get(random_key, False)),
            'min_key': min_key,
            'max_key': max_key,
            'random_key': random_key,
            'name': module_name
        }
    
    def save_all_settings():
        try:
            new_settings = {}
            
            for module_id, module_vars in vars_dict.items():
                min_val = float(module_vars['min'].get())
                max_val = float(module_vars['max'].get())
                random_val = module_vars['random'].get()
                
                new_settings[module_vars['min_key']] = min_val
                new_settings[module_vars['max_key']] = max_val
                new_settings[module_vars['random_key']] = random_val
                
                if min_val < 0 or max_val < 0:
                    messagebox.showerror("Ошибка", f"Значения для {module_vars['name']} не могут быть отрицательными!")
                    return
                
                if min_val > 100 or max_val > 100:
                    messagebox.showerror("Ошибка", f"Проценты для {module_vars['name']} не могут быть больше 100%!")
                    return
                if min_val > max_val and (min_val != 0 or max_val != 0):
                    messagebox.showerror("Ошибка", f"Минимальный процент {module_vars['name']} должен быть меньше максимального!")
                    return
            
            try:
                delay_min_val = float(delay_min_var.get())
                delay_max_val = float(delay_max_var.get())
                
                if delay_min_val < 0 or delay_max_val < 0:
                    messagebox.showerror("Ошибка", "Задержка не может быть отрицательной!")
                    return
                if delay_min_val > delay_max_val:
                    messagebox.showerror("Ошибка", "Минимальная задержка должна быть меньше максимальной!")
                    return
                
                new_settings['delay_min'] = delay_min_val
                new_settings['delay_max'] = delay_max_val
            except ValueError:
                messagebox.showerror("Ошибка", "Неверный формат задержки!")
                return
            
            try:
                retry_attempts_val = int(retry_attempts_var.get())
                
                if retry_attempts_val < 0:
                    messagebox.showerror("Ошибка", "Количество попыток не может быть отрицательным!")
                    return
                
                new_settings['max_retry_attempts'] = retry_attempts_val
            except ValueError:
                messagebox.showerror("Ошибка", "Неверный формат количества попыток!")
                return
            
            save_settings(new_settings)
            messagebox.showinfo("Успех", "Настройки сохранены!")
            root.destroy()
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат чисел!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")
    
    canvas = tk.Canvas(root)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    main_frame = ttk.Frame(scrollable_frame, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    title_label = ttk.Label(main_frame, text="⚙️ Настройки модулей", font=("Arial", 16, "bold"))
    title_label.pack(pady=(0, 20))
    
    for module_id, module_vars in vars_dict.items():
        frame = ttk.LabelFrame(main_frame, text=f"📦 {module_vars['name']}", padding="10")
        frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(frame, text="От (%):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=module_vars['min'], width=15).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(frame, text="До (%):").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(frame, textvariable=module_vars['max'], width=15).grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Label(frame, text="(0-100%, 0-0 = весь баланс)", font=("Arial", 8)).grid(row=1, column=0, columnspan=4, pady=2)
        
        ttk.Checkbutton(frame, text="Использовать случайный выбор", variable=module_vars['random']).grid(row=2, column=0, columnspan=4, pady=5)
    
    delay_frame = ttk.LabelFrame(main_frame, text="⏱️ Автоматический режим - Задержка между операциями", padding="10")
    delay_frame.pack(fill=tk.X, pady=10)
    
    delay_min_var = tk.StringVar(value=str(settings.get('delay_min', 1.0)))
    delay_max_var = tk.StringVar(value=str(settings.get('delay_max', 3.0)))
    
    ttk.Label(delay_frame, text="От (сек):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
    ttk.Entry(delay_frame, textvariable=delay_min_var, width=15).grid(row=0, column=1, padx=5, pady=5)
    
    ttk.Label(delay_frame, text="До (сек):").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
    ttk.Entry(delay_frame, textvariable=delay_max_var, width=15).grid(row=0, column=3, padx=5, pady=5)
    
    retry_frame = ttk.LabelFrame(main_frame, text="🔄 Повторные попытки неудачных транзакций", padding="10")
    retry_frame.pack(fill=tk.X, pady=10)
    
    retry_attempts_var = tk.StringVar(value=str(settings.get('max_retry_attempts', 3)))
    
    ttk.Label(retry_frame, text="Максимальное количество попыток:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
    ttk.Entry(retry_frame, textvariable=retry_attempts_var, width=15).grid(row=0, column=1, padx=5, pady=5)
    ttk.Label(retry_frame, text="(0 = без ограничений, повторять до 100% выполнения)", font=("Arial", 8)).grid(row=1, column=0, columnspan=2, pady=2)
    
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=20)
    
    ttk.Button(button_frame, text="💾 Сохранить", command=save_all_settings, width=20).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="❌ Отмена", command=root.destroy, width=20).pack(side=tk.LEFT, padx=5)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    root.mainloop()

def seed_to_private_key(seed_phrase):
    mnemo = Mnemonic("english")
    if not mnemo.check(seed_phrase):
        raise ValueError("Invalid seed")
    Account.enable_unaudited_hdwallet_features()
    account = Account.from_mnemonic(seed_phrase)
    return account.key.hex()

def check_connection(w3, max_wait_time=3600):
    """Проверяет соединение с RPC и ждет его восстановления при необходимости"""
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < max_wait_time:
        try:
            w3.eth.block_number
            if attempt > 0:
                print(f"✅ Соединение восстановлено!")
            return True
        except Exception as e:
            attempt += 1
            if attempt == 1:
                print(f"⚠️ Потеряно соединение с интернетом. Ожидание восстановления...")
            elif attempt % 10 == 0:
                elapsed = int(time.time() - start_time)
                print(f"⏳ Ожидание восстановления соединения... ({elapsed} сек)")
            
            time.sleep(5)
    
    print(f"❌ Превышено время ожидания восстановления соединения ({max_wait_time} сек)")
    return False

def wait_for_connection_and_retry(func, *args, max_retries=3, wait_between_retries=5, **kwargs):
    """Выполняет функцию с ожиданием восстановления соединения при ошибках"""
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            is_connection_error = any(keyword in error_str for keyword in [
                'connection', 'timeout', 'network', 'unreachable', 
                'refused', 'reset', 'failed to parse', 'no route to host'
            ])
            
            if is_connection_error and attempt < max_retries:
                print(f"⚠️ Ошибка соединения на попытке {attempt}/{max_retries}: {e}")
                print(f"🔄 Ожидание восстановления соединения...")
                
                w3 = None
                if args and hasattr(args[0], 'eth'):
                    w3 = args[0]
                elif 'w3' in kwargs:
                    w3 = kwargs['w3']
                
                if w3:
                    if check_connection(w3, max_wait_time=300):
                        print(f"🔄 Повторная попытка {attempt + 1}/{max_retries}...")
                        continue
                    else:
                        print(f"❌ Не удалось восстановить соединение")
                        return None
                else:
                    time.sleep(wait_between_retries)
                    continue
            else:
                if attempt < max_retries:
                    print(f"⚠️ Ошибка на попытке {attempt}/{max_retries}: {e}, повтор...")
                    time.sleep(wait_between_retries)
                else:
                    print(f"❌ Ошибка после {max_retries} попыток: {e}")
                    return None
    
    return None

def init_web3(proxy_url=None):
    try:
        if proxy_url:
            session = requests.Session()
            session.proxies = {"http": proxy_url, "https": proxy_url}
            w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 30}, session=session))
        else:
            w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 30}))
        
        if not check_connection(w3, max_wait_time=300):
            print(f"⚠️ Не удалось установить соединение при инициализации")
            return w3
        
        return w3
    except Exception as e:
        print(f"🔍 DEBUG: init_web3 exception: {e}")
        import traceback
        traceback.print_exc()
        if proxy_url:
            session = requests.Session()
            session.proxies = {"http": proxy_url, "https": proxy_url}
            w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 30}, session=session))
        else:
            w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={'timeout': 30}))
        
        check_connection(w3, max_wait_time=300)
        return w3

def wei_to_str(balance_wei):
    if balance_wei == 0:
        return "0"
    balance = balance_wei / 1e18
    return f"{balance:.6f}"

# Token addresses for swaps (will be extracted from transaction hashes)
TOKEN_ADDRESSES = {
    "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "cbBTC": "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",
    "cbETH": "0x2Ae3F1Ec7F1F5012CFEab0185bfc7aa3cf0DEc22",
    "CAKE": "0x4A9D6b95459eb9532B7E4c92Fc89f4c820bF8a77",
    "WELL": "0x4A9D6b95459eb9532B7E4c92Fc89f4c820bF8a77",
    "wstETH": "0xc1CBa3fCea344f92D9239c08C0568f6F2F0ee452",
    "weETH": "0x04C0599Ae5A44757c0af6F9eC3b93da8976c150A",
    "ZRO": "0x3Fb4a4fD2f9e2085b0b0F5e5C69b8e8b8c8b8c8b",
    "DEGEN": "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed",
    "AERO": "0x940181a94A35A4569E4529A3CDfB74e38FD98631",
    "Zora": "0x7d49a065D17d6d4a55dc13649901fdBB98B2AFc9",
    "Morpho": "0x4A9D6b95459eb9532B7E4c92Fc89f4c820bF8a77",
    "LMTS": "0x4A9D6b95459eb9532B7E4c92Fc89f4c820bF8a77",
    "tBTC": "0x236aa50979D5f3De3Bd1Eeb40E81137F22ab794b",
    "RECALL": "0x4A9D6b95459eb9532B7E4c92Fc89f4c820bF8a77",
    "MORPHO": "0x4A9D6b95459eb9532B7E4c92Fc89f4c820bF8a77",
    "yoETH": "0x4A9D6b95459eb9532B7E4c92Fc89f4c820bF8a77",
}

# Pendle market addresses
PENDLE_MARKETS = {
    "Kaito": "0x53fb20ff03ef94ef224557cc6262e0f11c20f718",
    "yoETH": "0x5d6e67fce4ad099363d062815b784d281460c49b",
    "yoUSD": "0xa679ce6d07cbe579252f0f9742fc73884b1c611c",
    "cbETH": "0x483f2e223c58a5ef19c4b32fbc6de57709749cb3",
    "yoEUR": "0xc25b8b6e56f403b690c0eac8a64c26af7689b49f",
}

# Beefy vault addresses
BEEFY_VAULTS = {
    "ZORA/wETH": "0x0000000000000000000000000000000000000000",
    "SOON/wETH": "0x0000000000000000000000000000000000000000",
    "wETH/USDC": "0x0000000000000000000000000000000000000000",
    "cbBTC/wETH": "0x0000000000000000000000000000000000000000",
    "AVNT/wETH": "0x0000000000000000000000000000000000000000",
    "rETH/USDC": "0x0000000000000000000000000000000000000000",
    "VIRTUAL/wETH": "0x0000000000000000000000000000000000000000",
}

# Compound cToken addresses
COMPOUND_CTOKENS = {
    "ETH": "0x1B0e765F6224C21223AeA2af16c1C46E38885a40",  # cETH
    "tBTC": "0x0000000000000000000000000000000000000000",
    "cbBTC": "0x0000000000000000000000000000000000000000",
    "wstETH": "0x0000000000000000000000000000000000000000",
}

# AAVE aToken addresses
AAVE_ATOKENS = {
    "USDC": "0x4e65fE4DbA92790696d040ac24Aa414708F5c0AB",
    "cbBTC": "0x0000000000000000000000000000000000000000",
    "cbETH": "0x0000000000000000000000000000000000000000",
    "wstETH": "0x0000000000000000000000000000000000000000",
    "tBTC": "0x0000000000000000000000000000000000000000",
}

# MoonWell mToken addresses
MOONWELL_MTOKENS = {
    "USDC": "0x0000000000000000000000000000000000000000",
    "cbBTC": "0x0000000000000000000000000000000000000000",
    "ETH": "0x0000000000000000000000000000000000000000",
    "cbETH": "0x0000000000000000000000000000000000000000",
    "MORPHO": "0x0000000000000000000000000000000000000000",
    "tBTC": "0x0000000000000000000000000000000000000000",
    "wstETH": "0x0000000000000000000000000000000000000000",
}

# Protocol execution functions
def execute_bungee_swap(w3, priv_key, token_out, amount_wei, auto_mode=False):
    """Swap ETH to token via Bungee (uses Uniswap V2 router on Base)"""
    try:
        account = w3.eth.account.from_key(priv_key)
        # Bungee использует Uniswap V2 router на Base (тот же, что и PancakeSwap)
        router_checksum = Web3.to_checksum_address(BUNGEE_ROUTER)
        token_out_checksum = Web3.to_checksum_address(TOKEN_ADDRESSES.get(token_out, token_out))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: Bungee Swap {eth_amount:.4f} ETH → {token_out}")
        
        balance = w3.eth.get_balance(account.address)
        if balance < amount_wei:
            print(f"❌ Недостаточно ETH!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        
        # Get gas prices
        gas_price = w3.eth.gas_price
        try:
            fee_history = w3.eth.fee_history(1, 'latest')
            if fee_history and fee_history.get('baseFeePerGas'):
                base_fee = fee_history['baseFeePerGas'][0]
                max_priority_fee = w3.to_wei('0.1', 'gwei')
                max_fee_per_gas = base_fee * 2 + max_priority_fee
            else:
                max_fee_per_gas = None
                max_priority_fee = None
        except:
            max_fee_per_gas = None
            max_priority_fee = None
        
        # Build swap transaction
        path = [WETH_TOKEN, token_out_checksum]
        deadline = int(time.time()) + 1200
        
        contract = w3.eth.contract(address=router_checksum, abi=UNISWAP_V2_ROUTER_ABI)
        
        # Рассчитываем ожидаемый выход и minOut с учетом slippage (0.5%)
        try:
            amounts_out = contract.functions.getAmountsOut(amount_wei, path).call()
            expected_out = amounts_out[-1]  # Последний элемент - это выходной токен
            slippage_tolerance = 0.995  # 0.5% slippage (99.5% от ожидаемого)
            min_out = int(expected_out * slippage_tolerance)
            print(f"📊 Ожидаемый выход: {expected_out / 1e18:.8f} {token_out}, minOut: {min_out / 1e18:.8f} {token_out} (0.5% slippage)")
        except Exception as e:
            print(f"⚠️  Не удалось рассчитать amountsOut: {e}")
            # Fallback: используем 1% от суммы как минимальный выход (очень консервативно)
            min_out = int(amount_wei * 0.01)
            print(f"⚠️  Используется fallback minOut: {min_out / 1e18:.8f} {token_out}")
        
        try:
            swap_gas = contract.functions.swapExactETHForTokens(
                min_out,
                path,
                account.address,
                deadline
            ).estimate_gas({'from': account.address, 'value': amount_wei})
            swap_gas = int(swap_gas * 1.2)
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            swap_gas = 200000
        
        swap_tx_params = {
            'from': account.address,
            'nonce': nonce,
            'gas': swap_gas,
            'value': amount_wei,
            'chainId': BASE_CHAIN_ID,
        }
        
        if max_fee_per_gas:
            swap_tx_params['maxFeePerGas'] = max_fee_per_gas
            swap_tx_params['maxPriorityFeePerGas'] = max_priority_fee
            swap_tx_params['type'] = 2
        else:
            swap_tx_params['gasPrice'] = gas_price
        
        swap_tx = contract.functions.swapExactETHForTokens(
            min_out,
            path,
            account.address,
            deadline
        ).build_transaction(swap_tx_params)
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    swap_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(swap_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Swap: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! Bungee swap выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        print(f"❌ FAILED после {max_retries} попыток!")
                        return False
            except Exception as e:
                if attempt < max_retries:
                    print(f"⚠️ Ошибка на попытке {attempt}: {e}, повтор...")
                    continue
                else:
                    print(f"❌ Ошибка после {max_retries} попыток: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        import traceback
        traceback.print_exc()
        return False

def execute_pancake_swap(w3, priv_key, token_out, amount_wei, auto_mode=False):
    """Swap ETH to token via PancakeSwap"""
    try:
        account = w3.eth.account.from_key(priv_key)
        router_checksum = Web3.to_checksum_address(PANCAKE_ROUTER)
        token_out_checksum = Web3.to_checksum_address(TOKEN_ADDRESSES.get(token_out, token_out))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: PancakeSwap {eth_amount:.4f} ETH → {token_out}")
        
        balance = w3.eth.get_balance(account.address)
        if balance < amount_wei:
            print(f"❌ Недостаточно ETH!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        path = [WETH_TOKEN, token_out_checksum]
        deadline = int(time.time()) + 1200
        
        contract = w3.eth.contract(address=router_checksum, abi=UNISWAP_V2_ROUTER_ABI)
        
        # Рассчитываем ожидаемый выход и minOut с учетом slippage (0.5%)
        try:
            amounts_out = contract.functions.getAmountsOut(amount_wei, path).call()
            expected_out = amounts_out[-1]  # Последний элемент - это выходной токен
            slippage_tolerance = 0.995  # 0.5% slippage (99.5% от ожидаемого)
            min_out = int(expected_out * slippage_tolerance)
            print(f"📊 Ожидаемый выход: {expected_out / 1e18:.8f} {token_out}, minOut: {min_out / 1e18:.8f} {token_out} (0.5% slippage)")
        except Exception as e:
            print(f"⚠️  Не удалось рассчитать amountsOut: {e}")
            # Fallback: используем 1% от суммы как минимальный выход (очень консервативно)
            min_out = int(amount_wei * 0.01)
            print(f"⚠️  Используется fallback minOut: {min_out / 1e18:.8f} {token_out}")
        
        try:
            swap_gas = contract.functions.swapExactETHForTokens(
                min_out,
                path,
                account.address,
                deadline
            ).estimate_gas({'from': account.address, 'value': amount_wei})
            swap_gas = int(swap_gas * 1.2)
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            swap_gas = 200000
        
        swap_tx = contract.functions.swapExactETHForTokens(
            min_out,
            path,
            account.address,
            deadline
        ).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': swap_gas,
            'gasPrice': gas_price,
            'value': amount_wei,
            'chainId': BASE_CHAIN_ID,
        })
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    swap_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(swap_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Swap: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! PancakeSwap выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return False
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    print(f"❌ Ошибка: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        return False

def execute_uniswap_swap(w3, priv_key, token_out, amount_wei, auto_mode=False):
    """Swap ETH to token via Uniswap V3"""
    try:
        account = w3.eth.account.from_key(priv_key)
        router_checksum = Web3.to_checksum_address(UNISWAP_ROUTER)
        token_out_checksum = Web3.to_checksum_address(TOKEN_ADDRESSES.get(token_out, token_out))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: Uniswap {eth_amount:.4f} ETH → {token_out}")
        
        balance = w3.eth.get_balance(account.address)
        if balance < amount_wei:
            print(f"❌ Недостаточно ETH!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        contract = w3.eth.contract(address=router_checksum, abi=UNISWAP_V3_ROUTER_ABI)
        
        # Рассчитываем ожидаемый выход через Quoter и minOut с учетом slippage (0.5%)
        amount_out_minimum = 0
        try:
            quoter_checksum = Web3.to_checksum_address(UNISWAP_V3_QUOTER)
            quoter_contract = w3.eth.contract(address=quoter_checksum, abi=UNISWAP_V3_QUOTER_ABI)
            
            # Пробуем разные fee tiers: 500 (0.05%), 3000 (0.3%), 10000 (1%)
            fee_tiers = [500, 3000, 10000]
            expected_out = 0
            selected_fee = 3000
            
            for fee in fee_tiers:
                try:
                    expected_out = quoter_contract.functions.quoteExactInputSingle(
                        WETH_TOKEN,
                        token_out_checksum,
                        fee,
                        amount_wei,
                        0
                    ).call()
                    selected_fee = fee
                    break
                except:
                    continue
            
            if expected_out > 0:
                slippage_tolerance = 0.995  # 0.5% slippage (99.5% от ожидаемого)
                amount_out_minimum = int(expected_out * slippage_tolerance)
                print(f"📊 Ожидаемый выход: {expected_out / 1e18:.8f} {token_out}, minOut: {amount_out_minimum / 1e18:.8f} {token_out} (0.5% slippage, fee: {selected_fee})")
            else:
                # Fallback: используем консервативную оценку
                amount_out_minimum = int(amount_wei * 0.01)
                print(f"⚠️  Не удалось получить quote, используется fallback minOut: {amount_out_minimum / 1e18:.8f} {token_out}")
        except Exception as e:
            print(f"⚠️  Ошибка при расчете quote: {e}")
            # Fallback: используем консервативную оценку
            amount_out_minimum = int(amount_wei * 0.01)
            selected_fee = 3000
            print(f"⚠️  Используется fallback minOut: {amount_out_minimum / 1e18:.8f} {token_out}")
        
        params = (
            WETH_TOKEN,
            token_out_checksum,
            selected_fee,  # Используем найденный fee tier
            account.address,
            int(time.time()) + 1200,
            amount_wei,
            amount_out_minimum,  # Используем рассчитанный minOut
            0
        )
        
        try:
            swap_gas = contract.functions.exactInputSingle(params).estimate_gas({
                'from': account.address,
                'value': amount_wei
            })
            swap_gas = int(swap_gas * 1.2)
        except Exception as e:
            print(f"⚠️  Gas estimation failed: {e}")
            swap_gas = 200000
        
        swap_tx = contract.functions.exactInputSingle(params).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': swap_gas,
            'gasPrice': gas_price,
            'value': amount_wei,
            'chainId': BASE_CHAIN_ID,
        })
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    swap_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(swap_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Swap: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! Uniswap swap выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return False
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    print(f"❌ Ошибка: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        return False

def execute_pendle_swap(w3, priv_key, market_name, view_type, amount_wei, auto_mode=False):
    """Swap on Pendle (YT or PT)"""
    try:
        account = w3.eth.account.from_key(priv_key)
        router_checksum = Web3.to_checksum_address(PENDLE_ROUTER)
        market_address = Web3.to_checksum_address(PENDLE_MARKETS.get(market_name, market_name))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: Pendle {view_type} {eth_amount:.4f} ETH → {market_name}")
        
        balance = w3.eth.get_balance(account.address)
        if balance < amount_wei:
            print(f"❌ Недостаточно ETH!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        contract = w3.eth.contract(address=router_checksum, abi=PENDLE_ROUTER_ABI)
        
        if view_type == "YT":
            function = contract.functions.swapExactSyForYt
        else:
            function = contract.functions.swapExactSyForPt
        
        try:
            swap_gas = function(
                account.address,
                account.address,
                market_address,
                amount_wei,
                0,
                0
            ).estimate_gas({'from': account.address, 'value': amount_wei})
            swap_gas = int(swap_gas * 1.2)
        except:
            swap_gas = 300000
        
        swap_tx = function(
            account.address,
            account.address,
            market_address,
            amount_wei,
            0,
            0
        ).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': swap_gas,
            'gasPrice': gas_price,
            'value': amount_wei,
            'chainId': BASE_CHAIN_ID,
        })
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    swap_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(swap_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Swap: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! Pendle {view_type} swap выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return False
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    print(f"❌ Ошибка: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        return False

def execute_compound_supply(w3, priv_key, token_name, amount_wei, auto_mode=False):
    """Supply to Compound"""
    try:
        account = w3.eth.account.from_key(priv_key)
        comptroller_checksum = Web3.to_checksum_address(COMPOUND_COMPTROLLER)
        ctoken_address = Web3.to_checksum_address(COMPOUND_CTOKENS.get(token_name, token_name))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: Compound Supply {eth_amount:.4f} {token_name}")
        
        balance = w3.eth.get_balance(account.address)
        if balance < amount_wei:
            print(f"❌ Недостаточно ETH!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        contract = w3.eth.contract(address=ctoken_address, abi=COMPOUND_ABI)
        
        if token_name == "ETH":
            function = contract.functions.mint
            params = []
            tx_value = amount_wei
        else:
            erc20 = w3.eth.contract(address=TOKEN_ADDRESSES.get(token_name, token_name), abi=ERC20_ABI)
            # Approve first
            approve_tx = erc20.functions.approve(ctoken_address, amount_wei).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': gas_price,
                'chainId': BASE_CHAIN_ID,
            })
            signed_approve = w3.eth.account.sign_transaction(approve_tx, priv_key)
            approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
            w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)
            
            function = contract.functions.mint
            params = [amount_wei]
            tx_value = 0
            nonce = w3.eth.get_transaction_count(account.address)
        
        try:
            supply_gas = function(*params).estimate_gas({'from': account.address, 'value': tx_value})
            supply_gas = int(supply_gas * 1.2)
        except:
            supply_gas = 200000
        
        supply_tx = function(*params).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': supply_gas,
            'gasPrice': gas_price,
            'value': tx_value,
            'chainId': BASE_CHAIN_ID,
        })
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    supply_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(supply_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Supply: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! Compound supply выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return False
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    print(f"❌ Ошибка: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        return False

def execute_beefy_deposit(w3, priv_key, vault_name, amount_wei, auto_mode=False):
    """Deposit to Beefy vault"""
    try:
        account = w3.eth.account.from_key(priv_key)
        vault_address = Web3.to_checksum_address(BEEFY_VAULTS.get(vault_name, vault_name))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: Beefy Deposit {eth_amount:.4f} ETH → {vault_name}")
        
        balance = w3.eth.get_balance(account.address)
        if balance < amount_wei:
            print(f"❌ Недостаточно ETH!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        contract = w3.eth.contract(address=vault_address, abi=BEEFY_VAULT_ABI)
        
        try:
            deposit_gas = contract.functions.deposit(amount_wei).estimate_gas({'from': account.address})
            deposit_gas = int(deposit_gas * 1.2)
        except:
            deposit_gas = 200000
        
        deposit_tx = contract.functions.deposit(amount_wei).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': deposit_gas,
            'gasPrice': gas_price,
            'chainId': BASE_CHAIN_ID,
        })
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    deposit_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(deposit_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Deposit: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! Beefy deposit выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return False
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    print(f"❌ Ошибка: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        return False

def execute_aave_supply(w3, priv_key, token_name, amount_wei, auto_mode=False):
    """Supply to AAVE"""
    try:
        account = w3.eth.account.from_key(priv_key)
        pool_checksum = Web3.to_checksum_address(AAVE_POOL)
        token_address = Web3.to_checksum_address(TOKEN_ADDRESSES.get(token_name, token_name))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: AAVE Supply {eth_amount:.4f} {token_name}")
        
        if token_name == "ETH":
            balance = w3.eth.get_balance(account.address)
            tx_value = amount_wei
        else:
            erc20 = w3.eth.contract(address=token_address, abi=ERC20_ABI)
            balance = erc20.functions.balanceOf(account.address).call()
            tx_value = 0
            # Approve first
            nonce = w3.eth.get_transaction_count(account.address)
            gas_price = w3.eth.gas_price
            approve_tx = erc20.functions.approve(pool_checksum, amount_wei).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': gas_price,
                'chainId': BASE_CHAIN_ID,
            })
            signed_approve = w3.eth.account.sign_transaction(approve_tx, priv_key)
            approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
            w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)
        
        if balance < amount_wei:
            print(f"❌ Недостаточно баланса!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        contract = w3.eth.contract(address=pool_checksum, abi=AAVE_POOL_ABI)
        
        try:
            supply_gas = contract.functions.supply(
                token_address if token_name != "ETH" else "0x0000000000000000000000000000000000000000",
                amount_wei,
                account.address,
                0
            ).estimate_gas({'from': account.address, 'value': tx_value})
            supply_gas = int(supply_gas * 1.2)
        except:
            supply_gas = 200000
        
        supply_tx = contract.functions.supply(
            token_address if token_name != "ETH" else "0x0000000000000000000000000000000000000000",
            amount_wei,
            account.address,
            0
        ).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': supply_gas,
            'gasPrice': gas_price,
            'value': tx_value,
            'chainId': BASE_CHAIN_ID,
        })
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    supply_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(supply_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Supply: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! AAVE supply выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return False
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    print(f"❌ Ошибка: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        return False

def execute_moonwell_supply(w3, priv_key, token_name, amount_wei, auto_mode=False):
    """Supply to MoonWell"""
    try:
        account = w3.eth.account.from_key(priv_key)
        comptroller_checksum = Web3.to_checksum_address(MOONWELL_COMPTROLLER)
        mtoken_address = Web3.to_checksum_address(MOONWELL_MTOKENS.get(token_name, token_name))
        
        eth_amount = amount_wei / 1e18
        print(f"\n🤖 {account.address}: MoonWell Supply {eth_amount:.4f} {token_name}")
        
        if token_name == "ETH":
            balance = w3.eth.get_balance(account.address)
            tx_value = amount_wei
        else:
            token_address = Web3.to_checksum_address(TOKEN_ADDRESSES.get(token_name, token_name))
            erc20 = w3.eth.contract(address=token_address, abi=ERC20_ABI)
            balance = erc20.functions.balanceOf(account.address).call()
            tx_value = 0
            # Approve first
            nonce = w3.eth.get_transaction_count(account.address)
            gas_price = w3.eth.gas_price
            approve_tx = erc20.functions.approve(mtoken_address, amount_wei).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': gas_price,
                'chainId': BASE_CHAIN_ID,
            })
            signed_approve = w3.eth.account.sign_transaction(approve_tx, priv_key)
            approve_hash = w3.eth.send_raw_transaction(signed_approve.raw_transaction)
            w3.eth.wait_for_transaction_receipt(approve_hash, timeout=300)
        
        if balance < amount_wei:
            print(f"❌ Недостаточно баланса!")
            return False
        
        nonce = w3.eth.get_transaction_count(account.address)
        gas_price = w3.eth.gas_price
        
        contract = w3.eth.contract(address=mtoken_address, abi=MOONWELL_COMPTROLLER_ABI)
        
        if token_name == "ETH":
            function = contract.functions.mint
            params = []
        else:
            function = contract.functions.mint
            params = [amount_wei]
        
        try:
            supply_gas = function(*params).estimate_gas({'from': account.address, 'value': tx_value})
            supply_gas = int(supply_gas * 1.2)
        except:
            supply_gas = 200000
        
        supply_tx = function(*params).build_transaction({
            'from': account.address,
            'nonce': nonce,
            'gas': supply_gas,
            'gasPrice': gas_price,
            'value': tx_value,
            'chainId': BASE_CHAIN_ID,
        })
        
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    print(f"🔄 Попытка {attempt}/{max_retries}...")
                    time.sleep(2)
                    supply_tx['nonce'] = w3.eth.get_transaction_count(account.address)
                
                signed_tx = w3.eth.account.sign_transaction(supply_tx, priv_key)
                tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                print(f"✅ Supply: {EXPLORER_URL}/tx/{w3.to_hex(tx_hash)}")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ УСПЕХ! MoonWell supply выполнен")
                    return True
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return False
            except Exception as e:
                if attempt < max_retries:
                    continue
                else:
                    print(f"❌ Ошибка: {e}")
                    return False
    except Exception as e:
        print(f"❌ {e}")
        return False

def execute_task_for_account(priv_key, proxy_url, action, manual_amount=None, auto_mode=False):
    """Execute task for a single account"""
    try:
        w3 = init_web3(proxy_url)
        
        try:
            block_number = wait_for_connection_and_retry(lambda: w3.eth.block_number, max_retries=1)
            if block_number is None:
                if not check_connection(w3, max_wait_time=600):
                    print(f"❌ Не удалось установить соединение с RPC")
                    return False
                block_number = w3.eth.block_number
        except Exception as e:
            print(f"❌ Web3 connection failed: {e}")
            if check_connection(w3, max_wait_time=600):
                print(f"✅ Соединение восстановлено, продолжаем работу")
            else:
                return False
        
        account = w3.eth.account.from_key(priv_key)
        
        balance = w3.eth.get_balance(account.address)
        settings = load_settings()
        
        # Calculate amount
        if manual_amount is not None and manual_amount > 0:
            amount_wei = int(manual_amount * 1e18)
        elif auto_mode:
            # Use random percentage from settings
            min_percent = settings.get(f"{action}_eth_min", 0.0)
            max_percent = settings.get(f"{action}_eth_max", 0.0)
            if min_percent == 0 and max_percent == 0:
                amount_wei = balance
            else:
                random_percent = random.uniform(min_percent, max_percent)
                random_percent = min(random_percent, 100.0)
                amount_wei = int(balance * random_percent / 100.0)
        else:
            amount_wei = balance
        
        # Проверяем только достаточность баланса для gas fees
        # На Base транзакции могут проходить даже с очень маленькими суммами (от 0.0000001 ETH)
        estimated_gas_cost = 200000 * w3.eth.gas_price  # Примерная стоимость gas для транзакции
        
        # Если баланс меньше чем нужно для gas, пропускаем
        if balance < estimated_gas_cost:
            print(f"⏭️  {account.address}: Недостаточно ETH для gas fees (баланс: {balance / 1e18:.8f} ETH, нужно: {estimated_gas_cost / 1e18:.8f} ETH)")
            return False
        
        # Если сумма + gas больше баланса, используем меньшую сумму (оставляем только для gas)
        if amount_wei + estimated_gas_cost > balance:
            amount_wei = balance - estimated_gas_cost
            # Проверяем, что после вычитания gas осталась хоть какая-то сумма (минимум 1 wei)
            if amount_wei <= 0:
                print(f"⏭️  {account.address}: Недостаточно ETH для транзакции (баланс: {balance / 1e18:.8f} ETH, нужно для gas: {estimated_gas_cost / 1e18:.8f} ETH)")
                return False
            print(f"📊 Сумма скорректирована с учетом gas: {amount_wei / 1e18:.8f} ETH (было запрошено больше)")
        
        # Убеждаемся, что amount_wei не равен 0 (минимум 1 wei для транзакции)
        if amount_wei <= 0:
            print(f"⏭️  {account.address}: Сумма транзакции слишком мала (amount_wei: {amount_wei})")
            return False
        
        # Execute based on action
        if action == "bungee":
            # Random token from Bungee list
            tokens = ["USDC", "RECALL", "MORPHO", "cbETH", "cbBTC", "tBTC", "WELL", "yoETH", "CAKE", "wstETH", "LMTS", "wBTC"]
            token = random.choice(tokens)
            return execute_bungee_swap(w3, priv_key, token, amount_wei, auto_mode)
        
        elif action == "pancake":
            # Random token from Pancake list
            tokens = ["USDC", "cbBTC", "cbETH", "CAKE", "WELL", "wstETH", "weETH", "ZRO", "DEGEN", "AERO"]
            token = random.choice(tokens)
            return execute_pancake_swap(w3, priv_key, token, amount_wei, auto_mode)
        
        elif action == "uniswap":
            # Random token from Uniswap list
            tokens = ["USDC", "cbBTC", "cbETH", "wstETH", "Zora", "Morpho", "LMTS", "tBTC"]
            token = random.choice(tokens)
            return execute_uniswap_swap(w3, priv_key, token, amount_wei, auto_mode)
        
        elif action == "pendle":
            # Random market and view type
            markets = ["Kaito", "yoETH", "yoUSD", "cbETH", "yoEUR"]
            market = random.choice(markets)
            view_type = random.choice(["YT", "PT"])
            return execute_pendle_swap(w3, priv_key, market, view_type, amount_wei, auto_mode)
        
        elif action == "compound":
            # Random token from Compound list
            tokens = ["ETH", "tBTC", "cbBTC", "wstETH"]
            token = random.choice(tokens)
            return execute_compound_supply(w3, priv_key, token, amount_wei, auto_mode)
        
        elif action == "beefy":
            # Random vault from Beefy list
            vaults = ["ZORA/wETH", "SOON/wETH", "wETH/USDC", "cbBTC/wETH", "AVNT/wETH", "rETH/USDC", "VIRTUAL/wETH"]
            vault = random.choice(vaults)
            return execute_beefy_deposit(w3, priv_key, vault, amount_wei, auto_mode)
        
        elif action == "aave":
            # Random token from AAVE list
            tokens = ["USDC", "cbBTC", "cbETH", "wstETH", "tBTC"]
            token = random.choice(tokens)
            return execute_aave_supply(w3, priv_key, token, amount_wei, auto_mode)
        
        elif action == "moonwell":
            # Random token from MoonWell list
            tokens = ["USDC", "cbBTC", "ETH", "cbETH", "MORPHO", "tBTC", "wstETH"]
            token = random.choice(tokens)
            return execute_moonwell_supply(w3, priv_key, token, amount_wei, auto_mode)
        
        return False
    
    except Exception as e:
        print(f"❌ {e}")
        return False

def generate_action_sequence():
    """Generate action sequence - сначала Bungee, Pancake, Uniswap (1,2,3), затем остальные"""
    # Обязательные первые три протокола
    priority_actions = ["bungee", "pancake", "uniswap"]
    random.shuffle(priority_actions)
    
    # Остальные протоколы
    other_actions = ["pendle", "compound", "beefy", "aave", "moonwell"]
    random.shuffle(other_actions)
    
    # Сначала приоритетные, затем остальные
    return priority_actions + other_actions

def execute_auto_mode_for_account(priv_key, proxy_url):
    """Execute auto mode for a single account"""
    try:
        w3 = init_web3(proxy_url)
        
        try:
            block_number = wait_for_connection_and_retry(lambda: w3.eth.block_number, max_retries=1)
            if block_number is None:
                if not check_connection(w3, max_wait_time=600):
                    print(f"❌ Не удалось установить соединение с RPC")
                    return False
                block_number = w3.eth.block_number
        except Exception as e:
            print(f"❌ Web3 connection failed: {e}")
            if check_connection(w3, max_wait_time=600):
                print(f"✅ Соединение восстановлено, продолжаем работу")
            else:
                return False
        
        account = w3.eth.account.from_key(priv_key)
        print(f"\n🤖 {account.address}: Автоматический режим")
        
        settings = load_settings()
        delay_min = settings.get('delay_min', 1.0)
        delay_max = settings.get('delay_max', 3.0)
        thread_delay = random.uniform(delay_min, delay_max)
        print(f"⏱️  Индивидуальная задержка для этого потока: {thread_delay:.2f} сек")
        
        action_sequence = generate_action_sequence()
        print(f"📋 Последовательность действий: {' → '.join(action_sequence)}")
        
        success_count = 0
        total_count = len(action_sequence)
        
        for i, action in enumerate(action_sequence, 1):
            print(f"\n[{i}/{total_count}] Выполнение: {action}")
            result = execute_task_for_account(priv_key, proxy_url, action, manual_amount=None, auto_mode=True)
            if result:
                success_count += 1
                print(f"✅ {action} выполнено успешно")
            else:
                print(f"❌ {action} не выполнено")
            
            if i < total_count:
                print(f"⏱️  Задержка: {thread_delay:.2f} сек")
                time.sleep(thread_delay)
        
        print(f"\n📊 Итого: {success_count}/{total_count} действий выполнено успешно")
        return success_count > 0
        
    except Exception as e:
        print(f"❌ Ошибка в автоматическом режиме: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_action(auth_type, action, max_workers=5, manual_amount=None):
    """Run action for all accounts"""
    create_files()
    
    items = load_from_file(FILES["seed"] if auth_type == "seed" else FILES["private"])
    if not items:
        print(f"❌ Нет {auth_type}")
        return
    
    proxies_raw = load_from_file(FILES["proxy"]) or [None]
    proxies = [normalize_proxy(p) for p in proxies_raw]
    
    priv_keys = []
    for item in items:
        if auth_type == "seed":
            try:
                priv_keys.append(seed_to_private_key(item))
            except:
                continue
        else:
            priv_keys.append(item)
    
    if not priv_keys:
        print("❌ Нет ключей")
        return
    
    account_proxy_pairs = []
    for i, priv_key in enumerate(priv_keys):
        proxy = proxies[i % len(proxies)] if proxies else None
        account_proxy_pairs.append((priv_key, proxy))
    
    random.shuffle(account_proxy_pairs)
    print(f"🔀 Кошельки будут обработаны в случайном порядке")
    
    priv_keys = [pair[0] for pair in account_proxy_pairs]
    proxies = [pair[1] for pair in account_proxy_pairs]
    
    if action == "auto":
        print(f"\n🚀 {len(priv_keys)} аккаунтов, режим: Автоматический")
        
        completed = 0
        failed_accounts = []
        successful_accounts = []
        
        account_addresses = {}
        for i, priv_key in enumerate(priv_keys):
            try:
                account = Web3().eth.account.from_key(priv_key)
                account_addresses[i] = account.address
            except:
                account_addresses[i] = f"Unknown_{i}"
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {executor.submit(execute_auto_mode_for_account, priv_keys[i], proxies[i]): i for i in range(len(priv_keys))}
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                account_address = account_addresses[index]
                try:
                    result = future.result()
                    if result:
                        completed += 1
                        successful_accounts.append(account_address)
                    else:
                        failed_accounts.append(account_address)
                except Exception as e:
                    failed_accounts.append(account_address)
                    print(f"🔍 DEBUG: Exception in future.result(): {e}")
        
        settings = load_settings()
        max_retry_attempts = settings.get('max_retry_attempts', 3)
        retry_count = 0
        
        while len(failed_accounts) > 0:
            if max_retry_attempts > 0 and retry_count >= max_retry_attempts:
                print(f"\n⚠️ Достигнуто максимальное количество попыток ({max_retry_attempts})")
                break
            
            retry_count += 1
            print(f"\n" + "=" * 60)
            print(f"🔄 ПОВТОРНАЯ ПОПЫТКА #{retry_count} (Автоматический режим)")
            if max_retry_attempts > 0:
                print(f"   Попытка {retry_count}/{max_retry_attempts}")
            else:
                print(f"   Попытка {retry_count} (без ограничений)")
            print(f"   Неудачных аккаунтов: {len(failed_accounts)}")
            print("=" * 60)
            
            retry_priv_keys = []
            retry_proxies = []
            retry_addresses = []
            
            for addr in failed_accounts:
                for idx, priv_key in enumerate(priv_keys):
                    try:
                        account = Web3().eth.account.from_key(priv_key)
                        if account.address.lower() == addr.lower():
                            retry_priv_keys.append(priv_key)
                            retry_proxies.append(proxies[idx])
                            retry_addresses.append(addr)
                            break
                    except:
                        continue
            
            retry_failed = []
            retry_successful = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                retry_future_to_index = {executor.submit(execute_auto_mode_for_account, retry_priv_keys[i], retry_proxies[i]): i for i in range(len(retry_priv_keys))}
                for future in as_completed(retry_future_to_index):
                    index = retry_future_to_index[future]
                    account_address = retry_addresses[index]
                    try:
                        result = future.result()
                        if result:
                            retry_successful.append(account_address)
                            if account_address in failed_accounts:
                                failed_accounts.remove(account_address)
                            if account_address not in successful_accounts:
                                successful_accounts.append(account_address)
                        else:
                            retry_failed.append(account_address)
                    except Exception as e:
                        retry_failed.append(account_address)
            
            failed_accounts = retry_failed
            
            print(f"\n📊 Результат попытки #{retry_count}:")
            print(f"   ✅ Успешно: {len(retry_successful)}")
            print(f"   ❌ Ошибки: {len(failed_accounts)}")
            
            if len(failed_accounts) == 0:
                print(f"\n🎉 Все транзакции выполнены успешно после {retry_count} попыток!")
                break
            
            if len(failed_accounts) > 0:
                delay = random.uniform(10, 30)
                print(f"\n⏱️  Задержка перед следующей попыткой: {delay:.2f} сек")
                time.sleep(delay)
        
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 60)
        if len(failed_accounts) == 0:
            print(f"✅ Все {len(successful_accounts)} аккаунтов отработали без ошибок!")
            if retry_count > 0:
                print(f"   (потребовалось {retry_count} повторных попыток)")
        else:
            print(f"✅ Успешно: {len(successful_accounts)}/{len(priv_keys)}")
            print(f"❌ Ошибки: {len(failed_accounts)}/{len(priv_keys)}")
            if retry_count > 0:
                print(f"   (выполнено {retry_count} повторных попыток)")
        print("=" * 60)
    else:
        print(f"\n🚀 {len(priv_keys)} аккаунтов, действие: {action}")
        
        completed = 0
        failed_accounts = []
        successful_accounts = []
        
        account_addresses = {}
        for i, priv_key in enumerate(priv_keys):
            try:
                account = Web3().eth.account.from_key(priv_key)
                account_addresses[i] = account.address
            except:
                account_addresses[i] = f"Unknown_{i}"
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {executor.submit(execute_task_for_account, priv_keys[i], proxies[i], action, manual_amount): i for i in range(len(priv_keys))}
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                account_address = account_addresses[index]
                try:
                    result = future.result()
                    if result:
                        completed += 1
                        successful_accounts.append(account_address)
                    else:
                        failed_accounts.append(account_address)
                except Exception as e:
                    failed_accounts.append(account_address)
        
        settings = load_settings()
        max_retry_attempts = settings.get('max_retry_attempts', 3)
        retry_count = 0
        
        while len(failed_accounts) > 0:
            if max_retry_attempts > 0 and retry_count >= max_retry_attempts:
                print(f"\n⚠️ Достигнуто максимальное количество попыток ({max_retry_attempts})")
                break
            
            retry_count += 1
            print(f"\n" + "=" * 60)
            print(f"🔄 ПОВТОРНАЯ ПОПЫТКА #{retry_count} (Действие: {action})")
            if max_retry_attempts > 0:
                print(f"   Попытка {retry_count}/{max_retry_attempts}")
            else:
                print(f"   Попытка {retry_count} (без ограничений)")
            print(f"   Неудачных аккаунтов: {len(failed_accounts)}")
            print("=" * 60)
            
            retry_priv_keys = []
            retry_proxies = []
            retry_addresses = []
            
            for addr in failed_accounts:
                for idx, priv_key in enumerate(priv_keys):
                    try:
                        account = Web3().eth.account.from_key(priv_key)
                        if account.address.lower() == addr.lower():
                            retry_priv_keys.append(priv_key)
                            retry_proxies.append(proxies[idx])
                            retry_addresses.append(addr)
                            break
                    except:
                        continue
            
            retry_failed = []
            retry_successful = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                retry_future_to_index = {executor.submit(execute_task_for_account, retry_priv_keys[i], retry_proxies[i], action, manual_amount): i for i in range(len(retry_priv_keys))}
                for future in as_completed(retry_future_to_index):
                    index = retry_future_to_index[future]
                    account_address = retry_addresses[index]
                    try:
                        result = future.result()
                        if result:
                            retry_successful.append(account_address)
                            if account_address in failed_accounts:
                                failed_accounts.remove(account_address)
                            if account_address not in successful_accounts:
                                successful_accounts.append(account_address)
                        else:
                            retry_failed.append(account_address)
                    except Exception as e:
                        retry_failed.append(account_address)
            
            failed_accounts = retry_failed
            
            print(f"\n📊 Результат попытки #{retry_count}:")
            print(f"   ✅ Успешно: {len(retry_successful)}")
            print(f"   ❌ Ошибки: {len(failed_accounts)}")
            
            if len(failed_accounts) == 0:
                print(f"\n🎉 Все транзакции выполнены успешно после {retry_count} попыток!")
                break
            
            if len(failed_accounts) > 0:
                delay = random.uniform(10, 30)
                print(f"\n⏱️  Задержка перед следующей попыткой: {delay:.2f} сек")
                time.sleep(delay)
        
        print("\n" + "=" * 60)
        print("📊 ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 60)
        if len(failed_accounts) == 0:
            print(f"✅ Все {len(successful_accounts)} аккаунтов отработали без ошибок!")
            if retry_count > 0:
                print(f"   (потребовалось {retry_count} повторных попыток)")
        else:
            print(f"✅ Успешно: {len(successful_accounts)}/{len(priv_keys)}")
            print(f"❌ Ошибки: {len(failed_accounts)}/{len(priv_keys)}")
            if retry_count > 0:
                print(f"   (выполнено {retry_count} повторных попыток)")
        print("=" * 60)

def main():
    """Main function"""
    create_files()
    print("\n" + "=" * 60)
    print("🔄 BASE_SOFT")
    print("=" * 60)
    
    main_choice = input("\n📋 Главное меню (1=Действия, 2=Настройки): ").strip()
    
    if main_choice == "2":
        settings_menu()
        return
    
    auth_choice = input("\n🔐 Источник (1=seed, 2=key): ").strip()
    auth_type = "seed" if auth_choice == "1" else "private"
    
    action_choice = input("\n📋 Действие (1=Bungee, 2=Pancake, 3=Uniswap, 4=Pendle, 5=Compound, 6=Beefy, 7=AAVE, 8=MoonWell, 9=Автоматический режим): ").strip()
    
    action_map = {
        "1": "bungee",
        "2": "pancake",
        "3": "uniswap",
        "4": "pendle",
        "5": "compound",
        "6": "beefy",
        "7": "aave",
        "8": "moonwell",
        "9": "auto"
    }
    
    action = action_map.get(action_choice)
    if not action:
        print("❌ Неверный выбор действия!")
        return
    
    manual_amount = None
    if action != "auto":
        settings = load_settings()
        use_random = settings.get(f'use_random_{action}', False)
        if use_random:
            print(f"✅ Используется случайная сумма из настроек")
        else:
            amount_input = input("\n💰 Сумма ETH (Enter=весь баланс): ").strip()
            manual_amount = float(amount_input) if amount_input else None
    
    threads_input = input("\n⚙️  Потоков (1-10): ").strip()
    max_workers = int(threads_input) if threads_input and 1 <= int(threads_input) <= 10 else 5
    
    run_action(auth_type, action, max_workers, manual_amount)

if __name__ == "__main__":
    main()
