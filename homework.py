import logging
import sys
import time
from os import getenv

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import TokenlessException

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)

logger.addHandler(handler)

PRACTICUM_TOKEN = getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 20
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщений в чат telegram."""
    
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Отправлено сообщение в чат telegram.')
    except Exception as error:
        logger.error('Сообщение не отправлено', error)

def get_api_answer(current_timestamp):
    """Запрос к API-сервису."""

    timestamp = current_timestamp 
    # or int(time.time())

    params = {'from_date': timestamp}

    response = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params
    )

    try:
        if response.status_code != 200:
            raise NoResponseException
    except NoResponseException as error:
        logger.error('Answer not, answer never', error)
        send_message(bot, 'no answer')

    return response.json()


def check_response(response):
    """Возвращает список домашних работ."""
    print(response)
    try:
        if response['homeworks'][0]:
            homeworks = response['homeworks']
            print('--------', homeworks, '------------------')
            logger.info('WITH CHECK RESPONSE ALL IS OK')

    except Exception as error:
        logger.error('empty homework', error)
        homeworks = []

    return homeworks
    

def parse_status(homework):
    if isinstance(homework, list):    
        homework = homework[0]

    if isinstance(homework, dict):

        if not homework.get('homework_name'):
                raise KeyError

        if homework.get('status') not in HOMEWORK_STATUSES:
                raise KeyError


        try:
            homework_name = homework.get('homework_name')
            homework_status = homework['status']

            verdict = HOMEWORK_STATUSES[homework_status]
        except KeyError as error:
            homework_name = 'unknown'
            verdict = 'unknown'

            
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'

    return 'no active homework'


def check_tokens():
    """Проверка доступности переменных окружения."""
    
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True

    return False

def main():
    """Основная логика работы бота."""
    
    bot = Bot(token=TELEGRAM_TOKEN)

    try:
        if not check_tokens():
            raise TokenlessException
    except TokenlessException as error:
        logger.critical('Токенов нет, не поедем', error)
        send_message(bot, 'tokenLESS')

    current_timestamp = 0
    #int(time.time())
    error_counter = 0
    current_status = ''
    
    check_tokens()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            message = parse_status(check_response(response))
            if message != current_status:
                send_message(bot, message)
                current_status = message

            current_timestamp = int(response['current_date'])
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if not error_counter:
                send_message(bot, message)
                error_counter += 1
            time.sleep(RETRY_TIME)
        else:
            pass


if __name__ == '__main__':
    main()
