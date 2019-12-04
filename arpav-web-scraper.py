import requests
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By


class TableCell:

    def __init__(self, cell_value, pollutant, meas_info, meas_unit, station_name, city_name, date):
        self.cell_value = cell_value
        self.pollutant = pollutant
        self.meas_info = meas_info
        self.meas_unit = meas_unit
        self.station_name = station_name
        self.city_name = city_name
        self.date = date


class ArpavArchiveScraper:

    arpav_air_data_archive_url = "https://www.arpa.veneto.it/arpavinforma/bollettini/aria/aria_dati_validati_storico.php"

    def __init__(self):
        # Using Firefox to access web
        self.driver = webdriver.Chrome()

    def select_day_date_on_archive_portal(self, city_name, date: datetime):

        selected_values = self._set_values_combo_box(city_name, date)

        # Open the website
        self.driver.get(self.arpav_air_data_archive_url)
        # Select the id box
        for box in ["provincia","giorno","mese","anno"]:
            comb_box = self.driver.find_element_by_name(box)
            comb_box.send_keys(str(selected_values[box]))
        go_button = self.driver.find_elements_by_xpath("//input[@name='Vai' and @value='Visualizza il bollettino']")[0]
        go_button.click()

    def get_data_from_table_by_cityname(self, station_name, city_name, date):
        """
        This function is meant to recreate and analyze the table on the website.
        The basic idea is to avoid to blindly pick the cell by its index, but trying to get that based on the pollutant
        it corresponds to (from first row), the measurement_info (2nd row) and measurement_unit (3rd row).
        In order to recognize and connect these columns with the table cells we had to analyze the x_coordinate of
        those cells.
        """

        # Retrieve data of the pollutants of the first row and the categories of the second row
        pollutant_list = [{'text': t.text, 'x': t.location['x']} for t in
                          self.driver.find_elements_by_xpath("//div[@id='ariadativalidati']/table/tbody/tr[1]/td")]
        # TODO Change the value of text so it can use the value of the child! that should be  ./span/a  . How can we do that?
        measurement_info = [{'text': t.find_element_by_tag_name("a").text,
                             'x': t.location['x']} for t in
                            self.driver.find_elements_by_xpath("//div[@id='ariadativalidati']/table/tbody/tr[2]/td")]
        # Reorganize the measurement_infos (like "max ora"/"media giorn."/... ) according
        # to the category and the pollutant they belong to
        for i in range(len(measurement_info)):
            for j in range(len(pollutant_list)):
                try:
                    if pollutant_list[j]['x'] <= measurement_info[i]['x'] < pollutant_list[j + 1]['x']:
                        measurement_info[i]['pollutant'] = pollutant_list[j]['text']
                        break
                except IndexError:
                    # This is happening for the last elements belonging to the last pollutant (where
                    # there is no further measurement_info[j + 1])
                    measurement_info[i]['pollutant'] = pollutant_list[j]['text']
                    break

        # ======== PART 2
        measurement_units = [{'meas_units': t.text, 'x': t.location['x']}  for t in
                             self.driver.find_elements_by_xpath("//div[@id='ariadativalidati']/table/tbody/tr[3]/td")]
        # Reorganize the measurement_units (like conc./ora/sup ) according to the category and the pollutant they belong to
        for i in range(len(measurement_units)):
            for j in range(len(measurement_info)):
                try:
                    if measurement_info[j]['x'] <= measurement_units[i]['x'] < measurement_info[j + 1]['x']:
                        measurement_units[i]['meas_info'] = measurement_info[j]['text']
                        measurement_units[i]['pollutant'] = measurement_info[j]['pollutant']
                        break
                except IndexError:
                    # This is happening for the last elements belonging to the last pollutant (where
                    # there is no further measurement_info[j + 1])
                    measurement_units[i]['meas_info'] = measurement_info[j]['text']
                    measurement_units[i]['pollutant'] = measurement_info[j]['pollutant']
                    break
        # The first three columns of measurement units are only metadata and we can discard them
        del measurement_units[:3]
        cityname_list = [t.text for t in self.driver.find_elements_by_xpath("//div[@id='ariadativalidati']/table/tbody/tr/td[2]/strong")]
        table_data = []
        # TODO: Think how we can arrange the table values in a good structure.
        #   Maybe a csv file that can be easily accessed by pandas???

        # ======== PART 3: Cell Values
        for i in range(len(measurement_units)):
            for j in range(len(cityname_list)):
                # I have to add 4 to row and col index because the indexing starts from 1 and because the
                # first 3 rows and columns are metadata
                cell_value = self.driver.find_elements_by_xpath(f"//div[@id='ariadativalidati']/table/tbody/tr[{j+4}]/td[{i+4}]")[0]
                table_data.append(TableCell(cell_value=cell_value.text,
                                            pollutant=measurement_units[i]['pollutant'],
                                            meas_info=measurement_units[i]['meas_info'],
                                            meas_unit=measurement_units[i]['meas_units'],
                                            station_name=cityname_list[j],
                                            city_name=city_name,
                                            date=date)
                                  )

        print(f"Done extracting table values for date: {date}")

    def _set_values_combo_box(self, city_name, date: datetime):
        #date.strftime('%d-%m-%y')
        return {
            "provincia": city_name,
            "giorno": '{:02d}'.format(date.day),
            "mese": '{:02d}'.format(date.month),
            "anno": str(date.year)
        }

    def retrieve_single_data_from_website(self, city_name, station_name, date: datetime):
        self.select_day_date_on_archive_portal(city_name=city_name, date=date)
        self.get_data_from_table_by_cityname(station_name=station_name, city_name=city_name, date=date)

if __name__ == "__main__":
    arpav_scraper = ArpavArchiveScraper()
    arpav_scraper.retrieve_single_data_from_website(city_name="Belluno",
                                                    station_name="BL - Parco Citta di Bologna",
                                                    date=datetime(2018,7,4))