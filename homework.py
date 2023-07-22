import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv


load_dotenv()


PRACTICUM_TOKEN = os.getenv('YPTOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class HTTPResponseError(Exception):
    """Исключение при ответе со статусом, отличным от 200."""


def check_tokens():
    """Доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено успешно!')
    except telegram.error.TelegramError as error:
        logger.error(f'Возникла ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API."""
    payload = {'from_date': timestamp}
    try:
        logger.debug('Запрос к эндпоинту API...')
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=payload
        )
    except requests.exceptions.RequestException as error:
        logger.error(f'Сбой при доступе к эндпоинту {ENDPOINT}: {error}')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise HTTPResponseError(
            f'Сбой при доступе к эндпоинту {ENDPOINT}.'
            f'Статус ответа: {homework_statuses.status_code}.'
        )
    try:
        homework_statuses = homework_statuses.json()
    except json.JSONDecodeError:
        logger.error('Сбой при приведениb ответа к типам данных Python')
    return homework_statuses


def check_response(response):
    """Проверка ответа API."""
    try:
        homework_statuses = response['homeworks']
    except KeyError as error:
        logger.error(f'Сбой при проверке ключей в ответе API ({error})')
    if not isinstance(homework_statuses, list):
        raise TypeError('Ответ API - не в виде списка')
    return homework_statuses


def parse_status(homework):
    """Извлечение статуса работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as error:
        raise KeyError(f'Сбой при проверке ключей в ответе API ({error})')
    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
    except KeyError as error:
        raise KeyError(
            f'Несоотвутствие статуса домашней работы '
            f'ответа API: {error}'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(
            'Отсутствует обязательная переменная окружения, '
            'программа принудительно остановлена.'
        )
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    send_message(bot, parse_status(homework))
            else:
                logger.debug('Программа сработала штатно.')
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
