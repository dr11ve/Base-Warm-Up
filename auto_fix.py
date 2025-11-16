#!/usr/bin/env python3
"""
Автоматическое исправление проверки минимального баланса в base_soft.py
"""

import os

script_dir = os.path.dirname(os.path.abspath(__file__))
base_soft_path = os.path.join(script_dir, 'base_soft.py')

if not os.path.exists(base_soft_path):
    print(f"❌ Файл base_soft.py не найден в {script_dir}")
    print("Убедитесь, что файл находится в той же директории, что и этот скрипт.")
    exit(1)

print(f"📝 Читаю файл: {base_soft_path}")

with open(base_soft_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Ищем строку с проверкой
found = False
new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # Ищем блок с проверкой минимального баланса
    if 'if amount_wei < int(0.001 * 1e18):' in line:
        found = True
        print(f"✅ Найдена проверка на строке {i+1}")
        
        # Пропускаем старые строки проверки
        new_lines.append("        # Минимум только для покрытия gas fees (примерно 0.00001 ETH)\n")
        new_lines.append("        min_balance_for_gas = int(0.00001 * 1e18)  # ~0.00001 ETH для gas\n")
        new_lines.append("        if balance < min_balance_for_gas:\n")
        new_lines.append("            print(f\"⏭️  {account.address}: Недостаточно ETH для gas fees (минимум 0.00001 ETH)\")\n")
        new_lines.append("            return False\n")
        new_lines.append("\n")
        new_lines.append("        # Проверяем, что суммы достаточно для транзакции (с учетом gas)\n")
        new_lines.append("        estimated_gas_cost = 200000 * w3.eth.gas_price  # Примерная стоимость gas\n")
        new_lines.append("        if amount_wei + estimated_gas_cost > balance:\n")
        new_lines.append("            # Если сумма + gas больше баланса, используем меньшую сумму\n")
        new_lines.append("            amount_wei = balance - estimated_gas_cost\n")
        new_lines.append("            if amount_wei < 0:\n")
        new_lines.append("                print(f\"⏭️  {account.address}: Недостаточно ETH для транзакции (нужно для gas)\")\n")
        new_lines.append("                return False\n")
        
        # Пропускаем следующие 2 строки (print и return False)
        i += 1
        if i < len(lines) and 'print(f"⏭️' in lines[i]:
            i += 1
        if i < len(lines) and 'return False' in lines[i]:
            i += 1
        continue
    
    new_lines.append(line)
    i += 1

if not found:
    print("⚠️  Проверка не найдена. Возможно, файл уже исправлен или имеет другую структуру.")
    print("Попробуйте исправить вручную, следуя инструкции в файле ИСПРАВЛЕНИЕ.txt")
    exit(1)

# Создаем резервную копию
backup_path = base_soft_path + '.backup'
with open(backup_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f"💾 Создана резервная копия: {backup_path}")

# Записываем исправленный файл
with open(base_soft_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Файл успешно исправлен!")
print("Теперь минимальный баланс для транзакций: 0.00001 ETH (только для gas fees)")

