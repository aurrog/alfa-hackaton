"""Машина состояний кредитной заявки.

Декларативная таблица переходов: кто (роль), из каких статусов, в какой статус.
Любое изменение статуса в системе проходит через `resolve()` — так гарантируется,
что заявка движется только по разрешённым маршрутам, а каждый переход
фиксируется в журнале событий (см. services/transitions.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.statuses import AppStatus as S


class Actor(StrEnum):
    CLIENT = "client"  # любой участник компании с доступом к заявке
    CLIENT_SIGNER = "client_signer"  # участник компании с правом подписи
    SYSTEM = "system"  # конвейер / планировщик
    ANALYST = "analyst"  # кредитный аналитик (в т.ч. старший)
    COMMITTEE = "committee"  # риск-менеджер / кредитный комитет


@dataclass(frozen=True)
class Transition:
    name: str
    sources: frozenset[S]
    target: S
    actors: frozenset[Actor]
    title: str  # как событие называется в ленте заявки


def _t(name: str, sources: set[S], target: S, actors: set[Actor], title: str) -> Transition:
    return Transition(name, frozenset(sources), target, frozenset(actors), title)


NON_TERMINAL_CLIENT_CANCELLABLE = {
    S.DRAFT, S.PENDING_SIGNATURE, S.INFO_REQUESTED, S.MANUAL_REVIEW, S.COMMITTEE_REVIEW,
}

TRANSITIONS: list[Transition] = [
    # --- клиентский путь до подачи
    _t("send_for_signature", {S.DRAFT}, S.PENDING_SIGNATURE, {Actor.CLIENT}, "Заявка передана на подпись руководителю"),
    _t("return_to_draft", {S.PENDING_SIGNATURE}, S.DRAFT, {Actor.CLIENT}, "Заявка возвращена на доработку"),
    _t("submit", {S.DRAFT, S.PENDING_SIGNATURE}, S.SUBMITTED, {Actor.CLIENT_SIGNER}, "Заявка подписана и отправлена в банк"),
    _t("cancel", NON_TERMINAL_CLIENT_CANCELLABLE, S.CANCELLED, {Actor.CLIENT_SIGNER}, "Заявка отозвана клиентом"),
    # --- автоматический конвейер
    _t("start_check", {S.SUBMITTED}, S.DATA_CHECK, {Actor.SYSTEM}, "Начата проверка полноты и корректности данных"),
    _t("start_enrichment", {S.DATA_CHECK}, S.ENRICHMENT, {Actor.SYSTEM}, "Данные проверены, запрошены сведения из внешних источников"),
    _t("start_scoring", {S.ENRICHMENT}, S.SCORING, {Actor.SYSTEM}, "Сведения получены, выполняется оценка"),
    _t("request_info", {S.DATA_CHECK, S.SCORING}, S.INFO_REQUESTED, {Actor.SYSTEM}, "Запрошена дополнительная информация"),
    _t("auto_offer", {S.SCORING}, S.OFFER_ISSUED, {Actor.SYSTEM}, "Автоматическое решение: предложение сформировано"),
    _t("auto_decline", {S.DATA_CHECK, S.ENRICHMENT, S.SCORING}, S.DECLINED, {Actor.SYSTEM}, "Автоматическое решение: отказ"),
    _t("refer", {S.ENRICHMENT, S.SCORING}, S.MANUAL_REVIEW, {Actor.SYSTEM}, "Заявка передана на рассмотрение специалисту"),
    # --- уточнения
    _t("client_answers", {S.INFO_REQUESTED}, S.DATA_CHECK, {Actor.CLIENT}, "Клиент предоставил информацию, заявка возвращена в работу"),
    # --- ручное рассмотрение
    _t("analyst_offer", {S.MANUAL_REVIEW}, S.OFFER_ISSUED, {Actor.ANALYST}, "Аналитик одобрил заявку"),
    _t("analyst_decline", {S.MANUAL_REVIEW}, S.DECLINED, {Actor.ANALYST}, "Аналитик отказал в выдаче"),
    _t("analyst_request_info", {S.MANUAL_REVIEW}, S.INFO_REQUESTED, {Actor.ANALYST}, "Аналитик запросил информацию у клиента"),
    _t("escalate", {S.MANUAL_REVIEW}, S.COMMITTEE_REVIEW, {Actor.ANALYST}, "Заявка вынесена на кредитный комитет"),
    _t("rerun", {S.MANUAL_REVIEW}, S.ENRICHMENT, {Actor.ANALYST}, "Аналитик перезапросил сведения из внешних источников"),
    _t("committee_offer", {S.COMMITTEE_REVIEW}, S.OFFER_ISSUED, {Actor.COMMITTEE}, "Кредитный комитет одобрил заявку"),
    _t("committee_decline", {S.COMMITTEE_REVIEW}, S.DECLINED, {Actor.COMMITTEE}, "Кредитный комитет отказал в выдаче"),
    _t("committee_return", {S.COMMITTEE_REVIEW}, S.MANUAL_REVIEW, {Actor.COMMITTEE}, "Комитет вернул заявку аналитику на доработку"),
    # --- предложение, подписание, выдача
    _t("accept_offer", {S.OFFER_ISSUED}, S.OFFER_ACCEPTED, {Actor.CLIENT_SIGNER}, "Клиент принял предложение"),
    _t("decline_offer", {S.OFFER_ISSUED, S.OFFER_ACCEPTED}, S.CLIENT_DECLINED, {Actor.CLIENT_SIGNER}, "Клиент отказался от предложения"),
    _t("sign_contract", {S.OFFER_ACCEPTED}, S.DISBURSEMENT, {Actor.CLIENT_SIGNER}, "Кредитный договор подписан"),
    _t("disbursed", {S.DISBURSEMENT}, S.ISSUED, {Actor.SYSTEM}, "Кредит выдан, деньги зачислены на счёт"),
    # --- сроки
    _t("expire", {S.OFFER_ISSUED, S.OFFER_ACCEPTED, S.INFO_REQUESTED}, S.EXPIRED, {Actor.SYSTEM}, "Истёк срок ожидания ответа клиента"),
]

BY_NAME: dict[str, Transition] = {t.name: t for t in TRANSITIONS}

# Подписант компании может всё, что может участник компании
ACTOR_IMPLIES: dict[Actor, set[Actor]] = {
    Actor.CLIENT_SIGNER: {Actor.CLIENT_SIGNER, Actor.CLIENT},
    Actor.CLIENT: {Actor.CLIENT},
    Actor.SYSTEM: {Actor.SYSTEM},
    Actor.ANALYST: {Actor.ANALYST},
    Actor.COMMITTEE: {Actor.COMMITTEE, Actor.ANALYST},
}


class TransitionError(Exception):
    def __init__(self, message: str, code: str = "invalid_transition"):
        super().__init__(message)
        self.code = code


def resolve(name: str, current: S | str, actor: Actor) -> Transition:
    """Проверить, что переход `name` допустим из статуса `current` для `actor`."""
    t = BY_NAME.get(name)
    if t is None:
        raise TransitionError(f"Неизвестный переход: {name}", "unknown_transition")
    current = S(current)
    if current not in t.sources:
        raise TransitionError(
            f"Действие «{t.title}» недоступно в статусе «{current.value}»", "invalid_transition"
        )
    if not (ACTOR_IMPLIES[actor] & t.actors):
        raise TransitionError(f"Недостаточно прав для действия «{t.title}»", "forbidden_transition")
    return t


def available_transitions(current: S | str, actor: Actor) -> list[Transition]:
    current = S(current)
    return [t for t in TRANSITIONS if current in t.sources and ACTOR_IMPLIES[actor] & t.actors]


def reachable_statuses() -> set[S]:
    seen = {S.DRAFT}
    frontier = [S.DRAFT]
    while frontier:
        s = frontier.pop()
        for t in TRANSITIONS:
            if s in t.sources and t.target not in seen:
                seen.add(t.target)
                frontier.append(t.target)
    return seen
