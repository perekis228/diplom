import os
import sys
import json
from typing import Dict
from functools import partial
from PyQt5.QtWidgets import QTableWidgetItem, QMenu, QAction, QTableWidget
from PyQt5.QtCore import Qt

mixins_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(mixins_dir)
sys.path.append(src_dir)

from src.logger import log_to_file
# noinspection PyUnresolvedReferences


class TableMixin:
    """Миксин для работы с таблицами (поиск, избранное, топ)"""

    def __init__(self):
        super().__init__()
        self.favorite_items_data = None
        self.current_search_text = None

    def update_search_table(self, items: list[Dict[str, str | None | int]]) -> None:
        """Обновление таблицы результатов поиска"""
        try:
            if not hasattr(self, 'search_table') or self.search_table is None:
                return

            self.search_table.blockSignals(True)
            self.search_table.setRowCount(0)

            if not items:
                self.search_table.blockSignals(False)
                return

            self.search_table.setRowCount(len(items))

            for row, item in enumerate(items):
                try:
                    shortname = str(item.get("shortname", ""))
                    shortname_item = QTableWidgetItem(shortname)
                    shortname_item.setTextAlignment(Qt.AlignCenter)
                    self.search_table.setItem(row, 0, shortname_item)

                    name = str(item.get("name", ""))
                    name_item = QTableWidgetItem(name)
                    name_item.setTextAlignment(Qt.AlignCenter)
                    name_item.setToolTip(name)
                    self.search_table.setItem(row, 1, name_item)

                    price = item.get("price")
                    if price is None:
                        price_str = "Н/Д"
                    elif isinstance(price, int):
                        price_str = f"{int(price):,}".replace(",", " ")
                    else:
                        try:
                            price_num = int(price)
                            price_str = f"{price_num:,}".replace(",", " ")
                        except (ValueError, TypeError):
                            price_str = str(price)

                    price_item = QTableWidgetItem(price_str)
                    price_item.setTextAlignment(Qt.AlignCenter)
                    self.search_table.setItem(row, 2, price_item)

                except Exception as e:
                    self.append_to_console(f"Ошибка при добавлении строки {row}")
                    log_to_file(f"Ошибка при добавлении строки {row} в search table: {e}", "ERROR")
                    continue

            self.search_table.blockSignals(False)

        except Exception as e:
            self.append_to_console(f"Ошибка при обновлении таблицы")
            log_to_file(f"Ошибка при обновлении таблицы search table: {e}", "ERROR")
        finally:
            try:
                self.search_table.blockSignals(False)
            except Exception as e:
                log_to_file(f"Ошибка разблокировки сигналов search table: {e}", "ERROR")

    def update_top_table(self) -> None:
        """Обновляет таблицу данными из top.json"""
        if self.top_table is None:
            self.append_to_console("Ошибка: таблица не инициализирована", "red")
            log_to_file("Ошибка: таблица top не инициализирована", "ERROR")
            return

        top_file = os.path.join(self.project_root, "data", "top.json")

        if not os.path.exists(top_file):
            self.append_to_console(f"Файл {top_file} не найден", "red")
            log_to_file(f"Файл {top_file} не найден", "ERROR")
            return

        try:
            with open(top_file, 'r', encoding='utf-8') as file:
                top = json.load(file).get("items", {})

            if not top:
                self.append_to_console("Нет данных для отображения в таблице", "yellow")
                log_to_file("Нет данных для отображения в таблице top")
                return

            self.top_table.setRowCount(len(top))

            for row, (shortname, item_data) in enumerate(top.items()):
                name_item = QTableWidgetItem(shortname)
                name_item.setToolTip(item_data.get("name", ""))
                name_item.setTextAlignment(Qt.AlignCenter)
                self.top_table.setItem(row, 0, name_item)

                price = item_data.get("avg24hPrice", 0)
                price_item = QTableWidgetItem(f"{price:,}".replace(",", " "))
                price_item.setTextAlignment(Qt.AlignCenter)
                self.top_table.setItem(row, 1, price_item)

            self.append_to_console(f"Таблица обновлена: {len(top)} предметов", "green")
            log_to_file(f"Таблица top обновлена: {len(top)} предметов")

        except json.JSONDecodeError as e:
            self.append_to_console(f"Ошибка чтения JSON", "red")
            log_to_file(f"Ошибка чтения JSON: {e}", "ERROR")
        except Exception as e:
            self.append_to_console(f"Ошибка при обновлении таблицы", "red")
            log_to_file(f"Ошибка при обновлении таблицы top: {e}", "ERROR")

    def update_favorite_table(self) -> None:
        """Обновление таблицы избранного"""
        try:
            if not hasattr(self, 'favorite_table') or self.favorite_table is None:
                return

            self.favorite_table.blockSignals(True)
            self.favorite_table.setRowCount(0)
            sorted_data = dict(sorted(self.favorite_items_data.items()))
            self.favorite_table.setRowCount(len(sorted_data))

            for row, (shortname, item) in enumerate(sorted_data.items()):
                try:
                    shortname_item = QTableWidgetItem(shortname)
                    shortname_item.setTextAlignment(Qt.AlignCenter)
                    self.favorite_table.setItem(row, 0, shortname_item)

                    name = str(item.get("name", ""))
                    name_item = QTableWidgetItem(name)
                    name_item.setTextAlignment(Qt.AlignCenter)
                    name_item.setToolTip(name)
                    self.favorite_table.setItem(row, 1, name_item)

                    price = item.get("price")
                    price_item = QTableWidgetItem(price)
                    price_item.setTextAlignment(Qt.AlignCenter)
                    self.favorite_table.setItem(row, 2, price_item)

                except Exception as e:
                    self.append_to_console(f"Ошибка при добавлении строки {row}")
                    log_to_file(f"Ошибка в favorite при добавлении строки {row}: {e}", "ERROR")
                    continue

            self.favorite_table.blockSignals(False)

        except Exception as e:
            self.append_to_console("Ошибка при обновлении таблицы")
            log_to_file(f"Ошибка при обновлении таблицы favorite: {e}", "ERROR")
        finally:
            try:
                self.search_table.blockSignals(False)
            except Exception as e:
                log_to_file(f"Ошибка разблокировки сигналов: {e}", "ERROR")

    def add_to_favorite(self, table: QTableWidget, row) -> None:
        """Добавление предмета в таблицу избранного"""
        try:
            short_name = table.item(row, 0).text()
            name = table.item(row, 1).text()
            price = table.item(row, 2).text()

            favorite_path = os.path.join(self.project_root, "data", "favorite.json")

            favorites = {}
            if os.path.exists(favorite_path):
                try:
                    with open(favorite_path, 'r', encoding='utf-8') as f:
                        favorites = json.load(f).get("items", {})
                except (json.JSONDecodeError, FileNotFoundError) as e:
                    log_to_file(f"Ошибка в файле favorite: {e}", "ERROR")
                    favorites = {}

            if short_name in favorites:
                self.append_to_console(f"Товар '{short_name}' уже есть в избранном")
                return

            favorites[short_name] = {
                "name": name,
                "price": price
            }

            to_load = {"items": favorites}
            with open(favorite_path, 'w', encoding='utf-8') as f:
                json.dump(to_load, f, ensure_ascii=False, indent=4)

            self.append_to_console(f"Товар '{short_name}' добавлен в избранное")
            log_to_file(f"Товар '{short_name}' добавлен в избранное")
            self.favorite_items_data = favorites
            self.update_favorite_table()

        except Exception as e:
            self.append_to_console(f"Не удалось сохранить в избранное")
            log_to_file(f"Не удалось сохранить в избранное: {str(e)}", "ERROR")

    def del_from_favorite(self, table: QTableWidget, row) -> None:
        """Удаление предмета из таблицы избранного"""
        try:
            short_name = table.item(row, 0).text()

            favorite_path = os.path.join(self.project_root, "data", "favorite.json")

            favorite = {}
            if os.path.exists(favorite_path):
                with open(favorite_path, 'r', encoding='utf-8') as f:
                    favorite = json.load(f).get("items", {})

            if short_name not in favorite:
                self.append_to_console(f"Товара '{short_name}' нет в избранном")
                return
            del favorite[short_name]

            to_save = {"items": favorite}
            with open(favorite_path, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, ensure_ascii=False, indent=4)

            self.favorite_items_data = favorite
            self.append_to_console(f"Товар '{short_name}' удалён из избранного")
            log_to_file(f"Товар '{short_name}' удалён из избранного")
            self.update_favorite_table()

        except Exception as e:
            self.append_to_console(f"Не удалось сохранить в избранное")
            log_to_file(f"Не удалось сохранить в избранное: {str(e)}", "ERROR")

    def clear_favorite(self) -> None:
        """Удаление всех предметов из таблицы избранного"""
        try:
            self.favorite_items_data.clear()
            favorite_path = os.path.join(self.project_root, "data", "favorite.json")

            to_load = {"items": self.favorite_items_data}
            if os.path.exists(favorite_path):
                with open(favorite_path, 'w', encoding='utf-8') as f:
                    json.dump(to_load, f)
            self.update_favorite_table()
            self.append_to_console("Избранное очищено")
            log_to_file("Избранное очищено")
        except Exception as e:
            self.append_to_console(f"Не удалось очистить избранное")
            log_to_file(f"Не удалось очистить избранное: {str(e)}")

    def perform_search(self, text: str) -> None:
        """Выполняет поиск с текущим текстом"""
        self.current_search_text = text

        if not self.current_search_text or len(text) < 2:
            self.search_table.setRowCount(0)
            self.search_results_label.setText("Найдено предметов: 0")
            return

        self.search_timer.start(300)

    def on_search_text_changed(self) -> None:
        """Обработчик изменения текста в поле поиска"""
        try:
            self.append_to_console(f"Поиск: '{self.current_search_text}'")

            if not hasattr(self, 'all_items_data') or not self.all_items_data:
                self.append_to_console("items_data пуст или не существует")
                return

            search_text = self.current_search_text.lower()
            filtered_items = []

            for item_shortname, item_data in self.all_items_data.items():
                try:
                    name = item_data.get("name", "")

                    if not isinstance(name, str):
                        name = str(name)

                    if search_text in item_shortname.lower() or search_text in name.lower():
                        price = item_data.get("price")

                        if price is None:
                            price = None
                        else:
                            try:
                                price = int(price)
                            except (ValueError, TypeError):
                                price = None

                        filtered_items.append({
                            "shortname": str(item_shortname),
                            "name": name,
                            "price": price
                        })
                except Exception as e:
                    self.append_to_console(f"Ошибка обработки предмета {item_shortname}")
                    log_to_file(f"Ошибка обработки предмета {item_shortname}: {e}", "ERROR")
                    continue

            try:
                filtered_items.sort(key=lambda x: (x["price"] is not None, x["price"] or 0), reverse=True)
            except Exception as e:
                self.append_to_console(f"Ошибка при сортировке")
                log_to_file(f"Ошибка при сортировке: {e}", "ERROR")

            self.update_search_table(filtered_items)
            self.search_results_label.setText(f"Найдено предметов: {len(filtered_items)}")

        except Exception as e:
            self.append_to_console(f"Ошибка в поиске")
            log_to_file(f"Ошибка в поиске: {e}", "ERROR")

    def show_context_menu(self, position: int):
        """Контекстное меню, которое вызывается при нажатии пкм по таблице"""
        table = self.sender()

        index = table.indexAt(position)

        if index.isValid():
            menu = QMenu()
            if table != self.favorite_table:
                add_to_favorite_action = QAction("Добавить в избранное", table)
                add_to_favorite_action.triggered.connect(partial(self.add_to_favorite, table, index.row()))
                menu.addAction(add_to_favorite_action)

            del_from_favorite_action = QAction("Удалить из избранного", table)
            del_from_favorite_action.triggered.connect(partial(self.del_from_favorite, table, index.row()))
            menu.addAction(del_from_favorite_action)
            menu.exec_(table.viewport().mapToGlobal(position))
