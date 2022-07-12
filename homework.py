import logging
import sys
import time
from http import HTTPStatus
from os import getenv

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import (EmptyHomeworkError, EmptyResponseError,
                        NoResponseError, SendError)

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

    try:
        response = response.json()
    except Exception as error:
        raise Exception(error)

    return response


def check_response(response):
    """Возвращает список домашних работ."""
    if not response:
        raise EmptyResponseError

    if not isinstance(response, dict):
        raise TypeError('Ответ сервера не является словарем')

    if not ('homeworks' in response and 'current_date' in response):
        raise KeyError('Ответ не содержит подходящих ключей')

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError(
            'Под ключем homeworks в ответе сервера не содержится списка'
        )

    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if not homework:
        raise EmptyHomeworkError

    if not isinstance(homework, dict):
        raise TypeError('Тип домашней работы отличен от словаря')

    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')

    if not homework_name:
        raise KeyError('Домашняя работа не содержит ключа homework_name')

    verdict = HOMEWORK_STATUSES.get(homework_status)

    if not verdict:
        raise KeyError('Статус домашней работы неизвестен')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def message_logging(current_report, perv_report, message):
    """Добавляет логирование и счетчик сообщений."""
    if current_report != perv_report:
        send_message(bot, message)
        logger.info('Отправлено сообщение в чат telegram.')
        perv_report = current_report.copy()

        return perv_report


def status_message(message, current_report):
    """Отправляет сообщение при изменении статуса."""
    if message != current_report['status']:
        send_message(bot, message)
        logger.info('Отправлено сообщение в чат telegram.')
        current_report['status'] = message
    else:
        logger.debug('Статус работы не изменился')

    return current_report


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Не хватает токенов'
        logger.critical(message)
        send_message(bot, message)
        logger.info('Отправлено сообщение в чат telegram.')
        sys.exit(message)

    current_timestamp = int(time.time())

    current_report = {
        'status': '',
        'messages/output': '',
    }

    perv_report = {}

    while True:
        try:
            response = get_api_answer(current_timestamp)
            logger.info('Отправлен запрос к API-сервису')
            message = parse_status(check_response(response)[0])
            logger.info('Проверка ответа сервера')
            current_report = status_message(message, current_report)

            current_timestamp = int(response['current_date'])

        except NoResponseError as error:
            message = 'No response'
            logger.error('No response', error)
            current_report['message'] = message
            perv_report = message_logging(
                current_report,
                perv_report,
                message
            )

        except EmptyResponseError as error:
            message = 'Empty response'
            logger.error(message, error)
            current_report['message'] = message
            perv_report = message_logging(
                current_report,
                perv_report,
                message
            )

        except EmptyHomeworkError as error:
            message = 'Empty homework'
            logger.error(message, error)
            current_report['message'] = message
            perv_report = message_logging(
                current_report,
                perv_report,
                message
            )

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            current_report['message'] = message
            perv_report = message_logging(
                current_report,
                perv_report,
                message
            )

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    bot = Bot(token=TELEGRAM_TOKEN)

    main()
