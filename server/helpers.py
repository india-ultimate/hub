from datetime import datetime, date


def calculate_startdate_enddate():
    current_datetime = datetime.now()
    current_year = current_datetime.year

    start_datetime = datetime(current_year, 4, 1)
    end_datetime = datetime(current_year + 1, 3, 31)

    if start_datetime <= current_datetime <= end_datetime:
        start_date = start_datetime.date()
        end_date = end_datetime.date()
    elif current_datetime < start_datetime:
        start_date = date(current_year - 1, 4, 1)
        end_date = date(current_year, 3, 31)

    start_date_str, end_date_str = start_date.strftime("%Y-%m-%d"), end_date.strftime(
        "%Y-%m-%d"
    )
    return start_date_str, end_date_str
