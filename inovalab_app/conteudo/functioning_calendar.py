"""Calendário institucional 2026/2, portado do InovaLab do monólito."""
from calendar import Calendar


_FUNCTIONING_CALENDAR_DETAILS = {
    (8, 5): ("feriado", "Feriado Municipal – Aniversário de Rio Verde"),
    (9, 7): ("feriado", "Feriado Nacional – Independência do Brasil"),
    (10, 12): ("feriado", "Feriado Nacional – Nossa Senhora Aparecida"),
    (11, 2): ("feriado", "Feriado Nacional – Finados"),
    (11, 15): ("feriado", "Feriado Nacional – Proclamação da República"),
    (11, 20): ("feriado", "Feriado Nacional – Dia da Consciência Negra"),
    (11, 21): ("recesso", "Recesso Institucional"),
}

for _day in range(13, 19):
    _FUNCTIONING_CALENDAR_DETAILS[(10, _day)] = (
        "recesso",
        "Recesso Institucional – Dia do Professor e Dia do Servidor Público",
    )


def functioning_calendar_months():
    calendar = Calendar(firstweekday=6)
    month_names = ("Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")
    months = []

    for month, name in zip(range(7, 13), month_names, strict=True):
        weeks = []
        for week in calendar.monthdatescalendar(2026, month):
            cells = []
            for day in week:
                details = _FUNCTIONING_CALENDAR_DETAILS.get((month, day.day))
                cells.append(
                    {
                        "date": day,
                        "is_current_month": day.month == month,
                        "status": details[0] if details and day.month == month else "",
                        "label": details[1] if details and day.month == month else "",
                    }
                )
            weeks.append(cells)
        months.append({"number": month, "name": name, "weeks": weeks})

    return months
