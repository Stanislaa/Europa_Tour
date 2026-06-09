"""Удаление ВСЕХ пользователей из таблицы users.

Таблица НЕ удаляется — очищаются только строки. Остальные таблицы
(countries, hotels, tours) не затрагиваются.

Запуск (из папки backend, с тем же DATABASE_URL, что и у сайта):
    python clear_users.py            # удалить пользователей
    python clear_users.py --cascade  # + удалить их брони и избранное

Зачем нужен --cascade:
    bookings.user_id ссылается на users.id. В PostgreSQL и MySQL простое
    удаление пользователей не пройдёт, пока на них ссылаются брони
    (нарушение внешнего ключа). В этом случае скрипт подскажет добавить
    --cascade — тогда сначала удаляются связанные брони и избранное.
    (В SQLite по умолчанию внешние ключи не проверяются, удаление пройдёт
    и без --cascade.)
"""
import sys
from sqlmodel import Session, select, delete
from sqlalchemy.exc import IntegrityError

from main import engine, User, Booking, Favorite

CASCADE = "--cascade" in sys.argv


def main() -> None:
    with Session(engine) as db:
        total = len(db.exec(select(User.id)).all())
        if total == 0:
            print("В таблице users нет записей — удалять нечего.")
            return

        if CASCADE:
            # Сначала убираем строки, которые ссылаются на пользователей.
            db.exec(delete(Favorite))
            db.exec(delete(Booking))

        try:
            db.exec(delete(User))
            db.commit()
        except IntegrityError:
            db.rollback()
            print(
                "Не удалось удалить: на пользователей ещё ссылаются брони "
                "(bookings). Запустите со флагом --cascade, чтобы сначала "
                "удалить связанные брони и избранное:\n"
                "    python clear_users.py --cascade"
            )
            sys.exit(1)

        print(f"Удалено пользователей: {total}. Таблица users сохранена.")


if __name__ == "__main__":
    main()
