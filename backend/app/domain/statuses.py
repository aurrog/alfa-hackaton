"""Статусы кредитной заявки и их метаданные.

Единый источник правды для бэкенда, интерфейса (через /api/v1/meta/state-machine)
и документации (scripts/gen_docs.py строит диаграмму из этого файла).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AppStatus(StrEnum):
    DRAFT = "draft"
    PENDING_SIGNATURE = "pending_signature"
    SUBMITTED = "submitted"
    DATA_CHECK = "data_check"
    ENRICHMENT = "enrichment"
    SCORING = "scoring"
    INFO_REQUESTED = "info_requested"
    MANUAL_REVIEW = "manual_review"
    COMMITTEE_REVIEW = "committee_review"
    OFFER_ISSUED = "offer_issued"
    OFFER_ACCEPTED = "offer_accepted"
    DISBURSEMENT = "disbursement"
    ISSUED = "issued"
    DECLINED = "declined"
    CLIENT_DECLINED = "client_declined"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Waiting(StrEnum):
    CLIENT = "client"
    BANK = "bank"
    SYSTEM = "system"
    NONE = "none"


# Укрупнённые шаги трекера для клиента (клиенту не нужно знать внутренние статусы)
CLIENT_STAGES: list[tuple[str, str]] = [
    ("application", "Заявка"),
    ("check", "Проверка данных"),
    ("assessment", "Оценка"),
    ("decision", "Решение"),
    ("signing", "Подписание"),
    ("disbursement", "Выдача"),
]


@dataclass(frozen=True)
class StatusMeta:
    label: str  # для сотрудника банка
    client_label: str  # для клиента
    client_hint: str  # что происходит / что делать — простыми словами
    stage: str  # шаг трекера клиента
    waiting: Waiting
    terminal: bool = False
    sla_hours: float | None = None  # норматив пребывания в статусе
    tone: str = "blue"  # цвет бейджа в интерфейсе


STATUS_META: dict[AppStatus, StatusMeta] = {
    AppStatus.DRAFT: StatusMeta(
        "Черновик", "Черновик", "Заполните анкету — всё сохраняется автоматически. Подписать и отправить заявку может руководитель или собственник.",
        "application", Waiting.CLIENT, tone="gray"),
    AppStatus.PENDING_SIGNATURE: StatusMeta(
        "Ожидает подписи клиента", "Ждёт подписи руководителя", "Заявка подготовлена и передана на подпись. Руководитель проверит данные, подпишет согласия и отправит заявку в банк.",
        "application", Waiting.CLIENT, tone="yellow"),
    AppStatus.SUBMITTED: StatusMeta(
        "Подана", "Заявка отправлена", "Заявка получена банком и поставлена в очередь на автоматическую проверку.",
        "check", Waiting.SYSTEM, sla_hours=0.25, tone="blue"),
    AppStatus.DATA_CHECK: StatusMeta(
        "Проверка полноты и корректности", "Проверяем данные", "Проверяем, что анкета заполнена полностью, а документы соответствуют выбранному продукту.",
        "check", Waiting.SYSTEM, sla_hours=0.25, tone="blue"),
    AppStatus.ENRICHMENT: StatusMeta(
        "Обогащение данными", "Запрашиваем сведения", "Получаем сведения о компании из ЕГРЮЛ/ЕГРИП и ФНС, кредитную историю из БКИ и данные об оборотах.",
        "assessment", Waiting.SYSTEM, sla_hours=0.5, tone="blue"),
    AppStatus.SCORING: StatusMeta(
        "Скоринг и решение", "Оцениваем заявку", "Рассчитываем кредитную оценку и подбираем условия, которые подходят вашему бизнесу.",
        "assessment", Waiting.SYSTEM, sla_hours=0.25, tone="blue"),
    AppStatus.INFO_REQUESTED: StatusMeta(
        "Запрошена информация у клиента", "Нужны уточнения", "Чтобы продолжить, нам не хватает информации. Выполните задачи ниже — заявка сразу вернётся в работу.",
        "check", Waiting.CLIENT, sla_hours=120, tone="orange"),
    AppStatus.MANUAL_REVIEW: StatusMeta(
        "Ручное рассмотрение (аналитик)", "Рассматривает специалист", "Заявку изучает кредитный специалист. Обычно это занимает до одного рабочего дня.",
        "decision", Waiting.BANK, sla_hours=8, tone="violet"),
    AppStatus.COMMITTEE_REVIEW: StatusMeta(
        "Кредитный комитет", "Рассматривает кредитный комитет", "Сумма требует коллегиального решения. Комитет рассматривает заявку в течение одного-двух рабочих дней.",
        "decision", Waiting.BANK, sla_hours=24, tone="violet"),
    AppStatus.OFFER_ISSUED: StatusMeta(
        "Предложение направлено клиенту", "Предложение готово", "Банк готов выдать кредит. Проверьте условия и примите предложение до истечения срока его действия.",
        "decision", Waiting.CLIENT, sla_hours=240, tone="green"),
    AppStatus.OFFER_ACCEPTED: StatusMeta(
        "Предложение принято, подписание", "Подпишите договор", "Договор сформирован по принятым условиям. Подпишите его простой электронной подписью прямо в кабинете.",
        "signing", Waiting.CLIENT, sla_hours=72, tone="green"),
    AppStatus.DISBURSEMENT: StatusMeta(
        "Выдача средств", "Перечисляем деньги", "Договор подписан. Открываем ссудный счёт и перечисляем деньги на расчётный счёт компании.",
        "disbursement", Waiting.SYSTEM, sla_hours=1, tone="teal"),
    AppStatus.ISSUED: StatusMeta(
        "Кредит выдан", "Деньги на счёте", "Кредит выдан. График платежей доступен в разделе «Кредиты».",
        "disbursement", Waiting.NONE, terminal=True, tone="teal"),
    AppStatus.DECLINED: StatusMeta(
        "Отказ", "Банк не может одобрить заявку", "Мы объяснили причины ниже и подсказали, что можно сделать, чтобы следующая заявка была одобрена.",
        "decision", Waiting.NONE, terminal=True, tone="red"),
    AppStatus.CLIENT_DECLINED: StatusMeta(
        "Клиент отказался от предложения", "Вы отказались от предложения", "Предложение отклонено. Вы можете подать новую заявку в любой момент.",
        "decision", Waiting.NONE, terminal=True, tone="gray"),
    AppStatus.CANCELLED: StatusMeta(
        "Отозвана клиентом", "Заявка отозвана", "Заявка отозвана. Черновик и введённые данные сохранены — их можно использовать в новой заявке.",
        "application", Waiting.NONE, terminal=True, tone="gray"),
    AppStatus.EXPIRED: StatusMeta(
        "Истёк срок", "Срок истёк", "Срок действия предложения или ответа на запрос истёк. Подайте новую заявку — данные компании подставятся автоматически.",
        "decision", Waiting.NONE, terminal=True, tone="gray"),
}

ACTIVE_BANK_STATUSES = {AppStatus.MANUAL_REVIEW, AppStatus.COMMITTEE_REVIEW}
TERMINAL_STATUSES = {s for s, m in STATUS_META.items() if m.terminal}
IN_PROGRESS_STATUSES = set(AppStatus) - TERMINAL_STATUSES - {AppStatus.DRAFT, AppStatus.PENDING_SIGNATURE}
PIPELINE_STATUSES = {AppStatus.SUBMITTED, AppStatus.DATA_CHECK, AppStatus.ENRICHMENT, AppStatus.SCORING}
