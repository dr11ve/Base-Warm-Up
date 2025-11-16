#!/usr/bin/env python3
"""
Скрипт для исправления проверки минимального баланса в base_soft.py
"""

import re
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
base_soft_path = os.path.join(script_dir, 'base_soft.py')

if not os.path.exists(base_soft_path):
    print(f"❌ Файл {base_soft_path} не найден!")
    exit(1)

with open(base_soft_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Заменяем старую проверку на новую
old_check = r'if amount_wei < int\(0\.001 \* 1e18\):\s+print\(f"⏭️  \{account\.address\}: Недостаточно ETH \(минимум 0\.001 ETH\)"\)\s+return False'

new_check = '''# Минимум только для покрытия gas fees (примерно 0.00001 ETH)
min_balance_for_gas = int(0.00001 * 1e18)  # ~0.00001 ETH для gas
if balance < min_balance_for_gas:
    print(f"⏭️  {account.address}: Недостаточно ETH для gas fees (минимум 0.00001 ETH)")
    return False

# Проверяем, что суммы достаточно для транзакции (с учетом gas)
estimated_gas_cost = 200000 * w3.eth.gas_price  # Примерная стоимость gas
if amount_wei + estimated_gas_cost > balance:
    # Если сумма + gas больше баланса, используем меньшую сумму
    amount_wei = balance - estimated_gas_cost
    if amount_wei < 0:
        print(f"⏭️  {account.address}: Недостаточно ETH для транзакции (нужно для gas)")
        return False'''

# Простая замена по тексту
if 'if amount_wei < int(0.001 * 1e18):' in content:
    # Находим блок с проверкой
    pattern = r'if amount_wei < int\(0\.001 \* 1e18\):.*?return False'
    
    replacement = '''# Минимум только для покрытия gas fees (примерно 0.00001 ETH)
min_balance_for_gas = int(0.00001 * 1e18)  # ~0.00001 ETH для gas
if balance < min_balance_for_gas:
    print(f"⏭️  {account.address}: Недостаточно ETH для gas fees (минимум 0.00001 ETH)")
    return False

# Проверяем, что суммы достаточно для транзакции (с учетом gas)
estimated_gas_cost = 200000 * w3.eth.gas_price  # Примерная стоимость gas
if amount_wei + estimated_gas_cost > balance:
    # Если сумма + gas больше баланса, используем меньшую сумму
    amount_wei = balance - estimated_gas_cost
    if amount_wei < 0:
        print(f"⏭️  {account.address}: Недостаточно ETH для транзакции (нужно для gas)")
        return False'''
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    with open(base_soft_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Файл исправлен!")
else:
    print("⚠️  Проверка не найдена в файле. Возможно, уже исправлено.")

