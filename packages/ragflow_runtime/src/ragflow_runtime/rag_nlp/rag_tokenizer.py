#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import re

try:
    import infinity.rag_tokenizer as _infinity_rag_tokenizer
except ImportError:  # pragma: no cover
    _infinity_rag_tokenizer = None


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]|[^\s]")


class _FallbackRagTokenizer:
    def tokenize(self, line: str) -> str:
        return " ".join(_TOKEN_PATTERN.findall(line or ""))

    def fine_grained_tokenize(self, tks: str) -> str:
        return tks

    def tag(self, token: str) -> str:
        if re.fullmatch(r"[\u4e00-\u9fff]+", token or ""):
            return "n"
        if re.fullmatch(r"[A-Za-z]+", token or ""):
            return "en"
        if re.fullmatch(r"[0-9]+", token or ""):
            return "m"
        return "x"

    def freq(self, token: str) -> int:
        return 1

    def _tradi2simp(self, text: str) -> str:
        return text

    def _strQ2B(self, text: str) -> str:
        return text


_BaseTokenizer = _infinity_rag_tokenizer.RagTokenizer if _infinity_rag_tokenizer is not None else _FallbackRagTokenizer


class RagTokenizer(_BaseTokenizer):

    def tokenize(self, line: str) -> str:
        try:
            from common import settings  # moved from the top of the file to avoid circular import
            doc_engine_infinity = settings.DOC_ENGINE_INFINITY
        except Exception:
            doc_engine_infinity = False
        if doc_engine_infinity:
            return line
        else:
            return super().tokenize(line)

    def fine_grained_tokenize(self, tks: str) -> str:
        try:
            from common import settings  # moved from the top of the file to avoid circular import
            doc_engine_infinity = settings.DOC_ENGINE_INFINITY
        except Exception:
            doc_engine_infinity = False
        if doc_engine_infinity:
            return tks
        else:
            return super().fine_grained_tokenize(tks)


def is_chinese(s):
    if _infinity_rag_tokenizer is not None:
        return _infinity_rag_tokenizer.is_chinese(s)
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def is_number(s):
    if _infinity_rag_tokenizer is not None:
        return _infinity_rag_tokenizer.is_number(s)
    return bool(re.fullmatch(r"[0-9]+", s or ""))


def is_alphabet(s):
    if _infinity_rag_tokenizer is not None:
        return _infinity_rag_tokenizer.is_alphabet(s)
    return bool(re.fullmatch(r"[A-Za-z]+", s or ""))


def naive_qie(txt):
    if _infinity_rag_tokenizer is not None:
        return _infinity_rag_tokenizer.naive_qie(txt)
    return _TOKEN_PATTERN.findall(txt or "")


tokenizer = RagTokenizer()
tokenize = tokenizer.tokenize
fine_grained_tokenize = tokenizer.fine_grained_tokenize
tag = tokenizer.tag
freq = tokenizer.freq
tradi2simp = tokenizer._tradi2simp
strQ2B = tokenizer._strQ2B
