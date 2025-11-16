# Исправление для base_soft.py
# Найдите функцию execute_task_for_account и замените проверку баланса:

# БЫЛО:
# if amount_wei < int(0.001 * 1e18):
#     print(f"⏭️  {account.address}: Недостаточно ETH (минимум 0.001 ETH)")
#     return False

# ДОЛЖНО БЫТЬ:
# Минимум только для покрытия gas fees (примерно 0.00001 ETH)
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
        return False

