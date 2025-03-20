from loguru import logger
import time
from config import config, Chains
from core.bot import Bot
from core.onchain import Onchain
from core.excel import Excel
from models.account import Account
from utils.inputs import input_pause, input_deposit_amount, input_cycle_pause, input_cycle_amount
from utils.logging import init_logger
from utils.utils import (random_sleep, get_accounts, select_profiles)
import random


def main():

    if not config.is_browser_run:
        config.is_browser_run = True
    init_logger()

    accounts = get_accounts()
    accounts_for_work = select_profiles(accounts)
    pause = input_pause()
    cycle_amount = input_cycle_amount()
    cycle_pause = input_cycle_pause()
    for i in range(cycle_amount):
        random.shuffle(accounts_for_work)
        for account in accounts_for_work:
            worker(account)
            random_sleep(pause)
        logger.success(f'Цикл {i + 1} завершен, обработано {len(accounts_for_work)} аккаунтов!')
        logger.info(f'Ожидание перед следующим циклом {cycle_pause} секунд!')
        random_sleep(cycle_pause)

def worker(account: Account) -> None:
    try:
        with Bot(account) as bot:
            activity(bot)
    except Exception as e:
        logger.critical(f"{account.profile_number} Ошибка при инициализации Bot: {e}")

def activity(bot: Bot):

    amount_input = random.uniform(0.05, 0.1)
    excel_report = Excel(bot.account, file='ChainbaseActivity.xlsx')
    chainbase_onchain = Onchain(bot.account, Chains.CHAINBASE_TESTNET)
    balance_before = chainbase_onchain.get_balance().ether
    if balance_before > amount_input:
        logger.warning(
            f'Баланс в сети {Chains.CHAINBASE_TESTNET.name.upper()}: {balance_before:.5f} ETH. Пополнение не требуется!')
        return


    sepolia_onchain = Onchain(bot.account, Chains.SEPOLIA_TESTNET)
    sepolia_balance = sepolia_onchain.get_balance(address=bot.account.address)
    deposit_amount = amount_input - balance_before
    if deposit_amount > sepolia_balance * 1.1:
        logger.error(
            f'Баланс в сети {Chains.SEPOLIA_TESTNET.name.upper()} недостаточный для перевода: {balance_before:.5f} ETH!')
        return

    bot.metamask.auth_metamask()
    bot.metamask.select_chain(Chains.SEPOLIA_TESTNET)
    bot.ads.open_url('https://testnet.bridge.chainbase.com/')
    random_sleep(5, 10)
    button_agree = bot.ads.page.get_by_role('button', name='Agree & continue')
    if button_agree.count():
        button_agree.click()

    connect_button = bot.ads.page.get_by_role('button', name='Connect')
    if connect_button.count():
        bot.ads.page.get_by_role('button', name='Connect').first.click()
        random_sleep(2, 3)
        bot.ads.page.get_by_text('MetaMask').click()
        bot.metamask.universal_confirm()
        random_sleep(2, 3)

    bot.ads.page.get_by_role('textbox').click()
    random_sleep(2, 3)
    bot.ads.page.keyboard.type(f'{deposit_amount:.5f}', delay=300)
    if bot.ads.page.locator('button', has_text='Insufficient ETH for gas').count():
        logger.error('Недостаточно средств для отправки транзакции!')
        return
    time.sleep(10)
    bot.ads.page.get_by_role('button', name='Review bridge').click()
    random_sleep(2, 3)
    bot.ads.page.get_by_role('button', name='Continue').click()
    if bot.ads.page.get_by_role('heading',
                                name="Make sure the wallet you're bridging to supports Chainbase Network Testnet").count():
        bot.ads.page.locator('#addressCheck').click()
        bot.ads.page.get_by_role('button', name='Continue').click()
    bot.ads.page.get_by_role('button', name='Start').click()
    bot.metamask.universal_confirm(windows=2, buttons=2)

    for _ in range(60):
        balance_after = chainbase_onchain.get_balance().ether
        if balance_after > balance_before:
            excel_report.set_cell('Address', f'{bot.account.address}')
            excel_report.set_date('Date')
            excel_report.set_cell(f'Sepolia Bridge', f'{deposit_amount:.5f}')
            logger.success('Транзакция прошла успешно! Данные записаны в таблицу SoneiumActivity.xlsx')
            break
        random_sleep(5, 10)
    else:
        logger.error('Транзакция не прошла!')
        raise Exception('Транзакция не прошла!')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.warning('Программа завершена вручную')