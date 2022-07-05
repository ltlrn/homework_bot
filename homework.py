import logging
import sys
import time
from http import HTTPStatus
from os import getenv

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import (EmptyResponseError, NoResponseError, SendError,
                        TokenlessError, WrongResponseError)

load_dotenv()

PRACTICUM_TOKEN = getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
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
    except Exception as error:
        raise SendError(error)


def get_api_answer(current_timestamp):
    """Запрос к API-сервису."""
    timestamp = current_timestamp or int(time.time())

    params = {'from_date': timestamp}

    response = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params
    )

    if response.status_code != HTTPStatus.OK:
        raise NoResponseError

    return response.json()


def check_response(response):
    """Возвращает список домашних работ."""
    if not response:
        raise EmptyResponseError

    if not isinstance(response['homeworks'][0], dict):
        raise WrongResponseError('not a dict')

    try:
        if response['homeworks'][0]:
            homeworks = response['homeworks']

    except Exception as error:
        homeworks = []
        raise Exception(error)

    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
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
        except KeyError:
            homework_name = 'unknown'
            verdict = 'unknown'

        return f'Изменился статус проверки работы "{homework_name}". {verdict}'

    return 'no active homework'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True

    return False


def message_logging(message_counter, index, message):
    """Добавляет логирование и счетчик сообщений."""
    if not message_counter[index]:
        send_message(bot, message)
        logger.info('Отправлено сообщение в чат telegram.')
        message_counter[index] += 1


def main():
    """Основная логика работы бота."""
    current_timestamp = int(time.time())
    message_counter = [0, 0, 0, 0]
    current_status = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            message = parse_status(check_response(response))
            if message != current_status:
                send_message(bot, message)
                logger.info('Отправлено сообщение в чат telegram.')
                current_status = message
            else:
                logger.debug('Статус работы не изменился')

            current_timestamp = int(response['current_date'])
            time.sleep(RETRY_TIME)

        except NoResponseError as error:
            message = 'No response'
            logger.error('No response', error)
            message_logging(message_counter, 0, message)

        except EmptyResponseError as error:
            message = 'Empty response'
            logger.error(message, error)
            message_logging(message_counter, 1, message)

        except WrongResponseError as error:
            message = 'Wrong response type'
            logger.error(message, error)
            message_logging(message_counter, 2, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            message_logging(message_counter, 3, message)
            time.sleep(RETRY_TIME)

        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    bot = Bot(token=TELEGRAM_TOKEN)

    try:
        if not check_tokens():
            raise TokenlessError

    except TokenlessError as error:
        logger.critical('Токенов нет, не поедем', error)
        send_message(bot, 'Не хватает токенов')
        logger.info('Отправлено сообщение в чат telegram.')

    main()
