import pickle
from datetime import datetime, timedelta, date
from functools import wraps
from typing import Any, Callable
from collections import UserDict


MAX_NAME_LENGTH = 21
PHONE_LENGTH = 10
DATE_FORMAT = "%d-%m-%Y"
WEEKEND_DAYS = (5, 6)


def input_error(func: Callable) -> Callable:
    """Decorator for handling user input errors."""

    @wraps(func)
    def inner(*args, **kwargs) -> str:
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            # Handle validation and argument errors
            return str(e)
        except KeyError as e:
            # Catches "Contact not found" errors
            return e.args[0]
        except IndexError:
            # In case len(args) was missed somewhere
            return "Enter user name."
        except Exception as e:
            # Any other unforeseen error
            return f"An unexpected error occurred: {e}"

    return inner


class Field:
    """Base class for contact fields."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def __str__(self) -> str:
        return str(self.value)


class Name(Field):
    """Contact name with basic validation."""

    def __init__(self, value: str) -> None:
        if len(value) > MAX_NAME_LENGTH:
            raise ValueError(
                f"Name must be at most {MAX_NAME_LENGTH} characters long."
            )
        super().__init__(value)


class Phone(Field):
    """Phone number with basic validation."""

    def __init__(self, value: str) -> None:
        if not value.isdigit() or len(value) != PHONE_LENGTH:
            raise ValueError("Phone number must be a 10-digit number.")
        super().__init__(value)


class Birthday(Field):
    """Birthday field with date validation."""

    def __init__(self, value: str) -> None:
        try:
            date_obj = datetime.strptime(value, DATE_FORMAT).date()
        except ValueError:
            if "-" not in value:
                raise ValueError(
                    f"Invalid date format. Use {DATE_FORMAT.replace('%', '')}."
                )
            raise ValueError(f"Invalid date: '{value}' does not exist.")

        super().__init__(date_obj)


class Record:
    """
    Represents a contact record with a name,
    list of phone numbers, and an optional birthday.
    """

    def __init__(self, name: str) -> None:
        self.name = Name(name)
        self.phones: list[Phone] = []
        self.birthday: Birthday | None = None

    def add_phone(self, phone: str) -> None:
        if self.find_phone(phone):
            raise ValueError("Phone already exists")
        self.phones.append(Phone(phone))

    def remove_phone(self, phone: str) -> None:
        phone_obj = self.find_phone(phone)
        if phone_obj is None:
            raise ValueError(f"Phone {phone} not found in this contact.")
        self.phones.remove(phone_obj)

    def edit_phone(self, old_phone: str, new_phone: str) -> None:
        phone_obj = self.find_phone(old_phone)
        if phone_obj is None:
            raise ValueError(f"Phone {old_phone} not found in this contact.")

        Phone(new_phone)  # Validate new phone first to avoid partial update
        self.remove_phone(old_phone)
        self.add_phone(new_phone)

    def find_phone(self, phone: str) -> Phone | None:
        for p in self.phones:
            if p.value == phone:
                return p
        return None

    def add_birthday(self, birthday: str) -> None:
        self.birthday = Birthday(birthday)


class AddressBook(UserDict):
    """Container for contact records."""

    def add_record(self, record: Record) -> None:
        self.data[record.name.value] = record

    def find(self, name: str) -> Record | None:
        return self.data.get(name)

    def delete(self, name: str) -> str:
        if name in self.data:
            del self.data[name]
            return f"Contact '{name}' has been deleted"
        else:
            raise KeyError(f"Contact '{name}' not found.")


def parse_input(user_input: str) -> tuple[str, ...]:
    """Parses the user input into a command and arguments."""
    return tuple(user_input.strip().split())


@input_error
def add_contact(args: list[str], book: AddressBook) -> str:
    """
    Add either a new contact with a name and phone number,
    or a phone number to an existing contact.

    Usage: add [name] [phone]
    """
    if len(args) < 2:
        raise ValueError("Usage: add [name] [phone]")

    name, phone, *_ = args
    record = book.find(name)
    message = "Contact updated."
    Phone(phone)  # Validate new phone first to avoid partial update
    if record is None:
        record = Record(name)
        book.add_record(record)
        message = "Contact added."

    record.add_phone(phone)
    return message


@input_error
def change_contact_phone(args: list[str], book: AddressBook) -> str:
    """
    Updates the phone number for an specified existing contact.

    Usage: change [name] [old_phone] [new_phone]
    """
    if len(args) < 3:
        raise ValueError("Usage: change [name] [old_phone] [new_phone]")
    name, old_phone, new_phone, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError(f"Contact '{name}' not found.")
    record.edit_phone(old_phone, new_phone)
    return "Contact phone number updated."


@input_error
def show_phone(args: list[str], book: AddressBook) -> str:
    """
    Shows the phone number for a specific contact.

    Usage: phone [name]
    """
    if len(args) < 1:
        raise ValueError("Usage: phone [name]")

    name, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError(f"Contact '{name}' not found.")
    return f"phones: {'; '.join(p.value for p in record.phones)}."


@input_error
def add_birthday(args: list[str], book: AddressBook) -> str:
    """
    Add or update the birthday for a specific contact.

    Usage: add-birthday [name] [birthday date]
    """
    message = "Contact's birthday added"
    if len(args) < 2:
        raise ValueError("Usage: add-birthday [name] [birthday date]")
    name, birthday_date, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError(f"Contact '{name}' not found.")
    if record.birthday:
        message = "Contact's birthday updated"
    record.add_birthday(birthday_date)
    return message


@input_error
def show_birthday(args: list[str], book: AddressBook) -> str:
    """
    Display the date of birth for the specified contact.

    Usage: show-birthday [name]
    """
    if len(args) < 1:
        raise ValueError("Usage: show-birthday [name]")
    name, *_ = args
    record = book.find(name)
    if record is None:
        raise KeyError(f"Contact '{name}' not found.")
    return str(record.birthday) if record.birthday else "Birthday not set."


def get_upcoming_birthdays(book: AddressBook) -> list[dict[str, str]]:
    """
    Finds birthdays within 7 days and carries over congratulations from weeks
    """
    today = date.today()
    upcoming: list[dict[str, str]] = []

    for record in book.data.values():
        if not record.birthday:
            continue

        try:
            birthday_this_year = record.birthday.value.replace(year=today.year)
        except ValueError:
            # Handle 29 February in non-leap year
            birthday_this_year = date(today.year, 2, 28)

        if birthday_this_year < today:
            try:
                birthday_this_year = birthday_this_year.replace(
                    year=today.year + 1
                )
            except ValueError:
                birthday_this_year = date(today.year + 1, 2, 28)

        days_diff = (birthday_this_year - today).days

        if 0 <= days_diff <= 7:
            congratulation_date = birthday_this_year

            if congratulation_date.weekday() in WEEKEND_DAYS:
                congratulation_date += timedelta(
                    days=7 - congratulation_date.weekday()
                )

            upcoming.append(
                {
                    "name": record.name.value,
                    "date": congratulation_date.strftime(DATE_FORMAT),
                }
            )

    return upcoming


def format_birthdays(upcoming: list[dict[str, str]]) -> str:
    """
    Displays a list of contacts with upcoming birthdays within the next 7 days.

    Usage: birthdays
    """
    if not upcoming:
        return "No upcoming birthdays in the next 7 days."

    header = f"{'Name':<21} | {'Congratulation Date':<21}"
    separator = "-" * 45

    lines = [separator, header, separator]

    for item in upcoming:
        lines.append(f"{item['name']:<21} | {item['date']:<21}")
        lines.append(separator)

    return "\n".join(lines)


def show_all(book: AddressBook) -> str:
    """
    Displays all saved contacts.

    Usage: all
    """
    if not book.data:
        return "Address book is empty."

    header = f"{'Name':<21} | {'Phone':<21}"
    separator = "-" * 45

    lines = [separator, header, separator]

    for record in book.data.values():
        phones = record.phones
        first_phone = phones[0].value if phones else "No phones"
        lines.append(f"{record.name.value:<21} | {first_phone:<21}")

        if len(phones) > 1:
            for phone in phones[1:]:
                lines.append(f'{"":<21} | {phone.value:<21}')
        lines.append(separator)

    return "\n".join(lines)


def delete_record(args: list[str], book: AddressBook) -> str:
    """
    Delete contact from AddressBook

    Usage: del [name]
    """
    if len(args) < 1:
        raise ValueError("Usage: del [name]")
    name, *_ = args

    return book.delete(name)


def command_list() -> None:
    """Displays all command."""
    print("-" * 45)
    print(f"{'add [name] [phone]':<26} - Add/Update contact")
    print(f"{'change [name] [old] [new]':<26} - Change phone number")
    print(f"{'phone [name]':<26} - Show contact's phones")
    print(f"{'all':<26} - Show all contacts")
    print(f"{'add-birthday [name] [date]':<26} - Add BD (DD-MM-YYYY)")
    print(f"{'show-birthday [name]':<26} - Show contact's birthday")
    print(f"{'birthdays':<26} - Show upcoming birthdays")
    print(f"{'del [name]':<26} - Delete contact")
    print(f"{'exit or close':<26} - Save and exit")
    print("-" * 45)


def save_data(book: AddressBook, filename: str = "addressbook.pkl") -> None:
    """Saves the address book data to a file using pickle."""
    with open(filename, "wb") as f:
        pickle.dump(book, f)


def load_data(filename: str = "addressbook.pkl") -> AddressBook:
    """Loads the address book data from a file using pickle."""
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return (
            AddressBook()
        )  # Return a new address book if the file is not found


def main() -> None:
    """Main loop for the assistant bot."""
    book = load_data()
    print("-" * 45)
    print("Welcome to the assistant bot!")
    print("I can help you manage your contacts and birthdays.")
    print("Type 'help' or '?' to see all available commands.")
    print("-" * 45)
    while True:
        try:
            user_input = input("Enter a command: ")
            if not user_input.strip():
                continue
        except KeyboardInterrupt:
            save_data(book)
            print("\nGood bye!")
            break

        parts = parse_input(user_input)
        command, args = parts[0].lower(), list(parts[1:])

        if command in ("close", "exit"):
            print("Good bye!")
            save_data(book)
            break
        elif command == "hello":
            print("How can I help you?")
        elif command in ("?", "help", "command"):
            command_list()
        elif command == "add":
            print(add_contact(args, book))
        elif command == "change":
            print(change_contact_phone(args, book))
        elif command == "phone":
            print(show_phone(args, book))
        elif command == "all":
            print(show_all(book))
        elif command == "add-birthday":
            print(add_birthday(args, book))
        elif command == "show-birthday":
            print(show_birthday(args, book))
        elif command == "birthdays":
            print(format_birthdays(get_upcoming_birthdays(book)))
        elif command == "del":
            print(delete_record(args, book))
        else:
            print("Invalid command.")


if __name__ == "__main__":
    main()
