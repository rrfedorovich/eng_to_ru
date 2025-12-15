import logging
import re
import time

from typing import List, Iterator

from deep_translator import GoogleTranslator


class Translator:
    """Класс для перевода текста с английского на русский."""

    def __init__(
        self, batch_size: int = 5, log_prefix: str = ">", max_retries: int = 2
    ) -> None:
        """
        Инициализатор.

        Аргументы:
            batch_size: int - максимальное количество одновременно переводимых блоков текста (блок <= 5k символов). Больше - быстрее.
            log_prefix: str - префикс для сообщений логов.
            max_retries: int - максимальное число попыток перевода участка текста.
        """

        self._batch_size: int = batch_size
        self._translator: GoogleTranslator = GoogleTranslator(source="en", target="ru")
        self._log_prefix: str = log_prefix
        self._max_retries: int = max_retries

    @staticmethod
    def is_digits_and_punctuation(text: str) -> bool:
        """
        Проверяет, состоит ли строка только из цифр, пробельных и пунктуационных символов.

        Аргументы:
            text: str - текст, который нужно проверить на наличие лишь цифр, пунктуационных и пробельных символов.

        Возвращает:
            : bool - True, если цифры/знаки; False - иначе.
        """

        pattern = r'^[0-9.,;:!?\-()\[\]{}\'"\s]+$'
        return bool(re.fullmatch(pattern, text))

    def _prepare(self, text: str) -> Iterator[str]:
        """
        Разбивает текст на блоки не больше 5k символов.

        Аргументы:
            text: str - текст, который нужно разбить на блоки.

        Возвращает:
            : Iterator[str] - последовательность блоков текста, каждый не длиннее 5k символов.
        """

        tmp = ""
        for paragraph in text.split("\n"):
            if len(paragraph) + len(tmp) + 2 >= 5000:
                yield tmp[:-1]
                tmp = ""
            tmp += paragraph + "\n"
        yield tmp[:-1]

    def _get_batches(self, data_iterator: Iterator[str]) -> Iterator[List[str]]:
        """
        Разбивает data_iterator на списки блоков текста, каждый блок не длиннее 5k символов.
        Количество блоков в каждом списке: не больше self._batch_size.

        Аргументы:
            data_iterator:Iterator[str] - последовательность блоков текста, каждый блок длинной не больше 5k символов.

        Возвращает:
            : Iterator[List[str]] - последовательность списков по self._batch_size (и меньше) блоков текста не длиннее 5k символов.
        """

        batch: List[str] = []
        for i, text in enumerate(data_iterator):
            batch.append(text)
            if (i + 1) % self._batch_size == 0:
                yield batch
                batch = []
        if batch:
            yield batch

    def _translate(self, text: str) -> str | None:
        """
        Перевод текста по фрагментам с обработкой ошибок и повторными попытками.

        Аргументы:
            text: str - что переводит.

        Возворащает:
            : str - переведенный текст.
            : None - если возникли проблемы с переводом.
        """

        answer = ""
        batches_iterator = self._get_batches(self._prepare(text))
        len_of_translated_text = 0
        len_of_text = len(text)

        logging.info(f"{self._log_prefix}> Длина текста: {len(text)} символов.")

        for batch in batches_iterator:
            retries = 0
            success = False

            while retries < self._max_retries and not success:
                try:
                    blocks_sizes = [len(i) for i in batch]
                    answer += "\n".join(self._translator.translate_batch(batch))
                    len_of_translated_text += sum(blocks_sizes) + len("\n") * (
                        len(batch) - 1
                    )

                    logging.info(
                        f"{self._log_prefix}> Переведено: {int(len_of_translated_text/len_of_text*100)}%."
                    )
                    success = True

                except Exception as e:
                    retries += 1
                    logging.error(f"{self._log_prefix}> Ошибка при переводе: {e}.")
                    logging.error(
                        f"{self._log_prefix}> Попытка {retries} из {self._max_retries}."
                    )
                    if retries < self._max_retries:
                        time.sleep(10)  # Ожидание 10 секунд перед повторной попыткой
                    else:
                        logging.error(
                            f"{self._log_prefix}> Превышено максимальное количество попыток. Остановка программы."
                        )
                        return None

        return answer

    def run(self, text: str, description: str = "Перевод...") -> str | None:
        """
        Запускает перевод.

        Аргументы:
            text: str - что переводится.
            description: str - краткое текстовое приветствие-описание для системы логирования (на логику не влияет).

        Возворащает:
            : str - переведенный текст
            : None - если возникли проблемы с переводом.
        """

        logging.info("---")
        logging.info(f"{self._log_prefix} {description}")
        if self.is_digits_and_punctuation(text):
            logging.info(f"{self._log_prefix}> Переведено: 100%.")
            return text
        return self._translate(text)
