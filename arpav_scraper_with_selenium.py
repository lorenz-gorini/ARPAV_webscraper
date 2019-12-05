import csv
import datetime
from selenium import webdriver
import os


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

    def _select_day_date_on_archive_portal(self, city_name, date: datetime):

        selected_values = self._set_values_combo_box(city_name, date)

        # Open the website
        self.driver.get(self.arpav_air_data_archive_url)
        # Select the id box
        for box in ["provincia","giorno","mese","anno"]:
            comb_box = self.driver.find_element_by_name(box)
            comb_box.send_keys(str(selected_values[box]))
        go_button = self.driver.find_elements_by_xpath("//input[@name='Vai' and @value='Visualizza il bollettino']")[0]
        go_button.click()

    def _get_data_from_table_by_cityname(self, writer, city_name, date):
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
        if pollutant_list != []:

            measurement_info = [{'text': t.find_element_by_tag_name("a").text,
                                 'x': t.location['x']} for t in
                                self.driver.find_elements_by_xpath("//div[@id='ariadativalidati']/table/tbody/tr[2]/td")]
            self._link_meas_info_to_pollutant_columns(pollutant_list=pollutant_list,
                                                      measurement_info=measurement_info)

            measurement_units = [{'meas_units': t.text, 'x': t.location['x']}  for t in
                                 self.driver.find_elements_by_xpath("//div[@id='ariadativalidati']/table/tbody/tr[3]/td")]
            self._link_meas_units_to_meas_info_columns(measurement_info=measurement_info,
                                                       measurement_units=measurement_units)

            # The first three columns of measurement units are only metadata and we can discard them
            del measurement_units[:3]

            cityname_list = [t.text for t in self.driver.find_elements_by_xpath("//div[@id='ariadativalidati']/table/tbody/tr/td[2]/strong")]

            # STORE CELL VALUES
            for i in range(len(measurement_units)):
                for j in range(len(cityname_list)):
                    # I have to add 4 to row and col index because the indexing starts from 1 and because the
                    # first 3 rows and columns are metadata
                    cell_value = self.driver.find_elements_by_xpath(f"//div[@id='ariadativalidati']/table/"
                                                                    f"tbody/tr[{j+4}]/td[{i+4}]")[0]
                    writer.writerow({
                        'cell_value': cell_value.text,
                        'pollutant': measurement_units[i]['pollutant'],
                        'meas_info': measurement_units[i]['meas_info'],
                        'meas_unit': measurement_units[i]['meas_units'],
                        'station_name': cityname_list[j],
                        'city_name': city_name,
                        'date': date
                    })

            print(f"Done extracting table values for date: {date}")
            return 1
        else:
            print(f"There is no air pollution info for the date {date}")
            return 0

    def _set_values_combo_box(self, city_name, date: datetime):

        return {
            "provincia": city_name,
            "giorno": '{:02d}'.format(date.day),
            "mese": '{:02d}'.format(date.month),
            "anno": str(date.year)
        }

    def _link_meas_info_to_pollutant_columns(self, pollutant_list, measurement_info):

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

    def _link_meas_units_to_meas_info_columns(self, measurement_info, measurement_units):

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

    def retrieve_and_write_single_data_from_website(self, writer, city_name, date: datetime):
        self._select_day_date_on_archive_portal(city_name=city_name, date=date)
        return_code = self._get_data_from_table_by_cityname(writer=writer, city_name=city_name, date=date)
        return return_code

class DataArchive:

    def __init__(self, fieldnames, arpav_archives_dir):
        self.csv_file, self.writer = None, None
        self.fieldnames = fieldnames
        self.arpav_archives_dir = arpav_archives_dir

    def _prepare_writer(self, day_date, arpav_file_dir):
        # Open the csv file and initialize the csv_writer
        if self.csv_file is not None:
            self.csv_file.close()
        year_month_dir = os.path.join(self.arpav_archives_dir, f'{day_date.year}/{day_date.month}')

        # If the directory does not exist, create it
        if not os.path.exists(year_month_dir):
            os.makedirs(year_month_dir)

        self.csv_file = open(arpav_file_dir, mode="w+")
        self.writer = csv.DictWriter(self.csv_file, fieldnames=self.fieldnames)
        self.writer.writeheader()


    def scrape_and_archive_data_by_year(self, starting_date: datetime.datetime, last_year:int):
        arpav_scraper = ArpavArchiveScraper()
        extracted_values = 0
        missing_value_dates = []
        for day_id in range(365 * (last_year - starting_date.year)):
            day_date = starting_date + datetime.timedelta(days=day_id)
            arpav_file_dir = os.path.join(arpav_archives_dir,
                                          f'{day_date.year}/{day_date.month}',
                                          f'{day_date.year}_{day_date.month}_arpav_data.csv')
            if not os.path.exists(arpav_file_dir):
                self._prepare_writer(day_date=day_date, arpav_file_dir=arpav_file_dir)
            if self.writer is None:
                # The file is already there. Delete it first
                print(f"ERROR: There is already a file named: {arpav_file_dir}. Delete it and restart the script.")
            extracted_values += arpav_scraper.retrieve_and_write_single_data_from_website(writer=self.writer,
                                                                                          city_name="Belluno",
                                                                                          date=day_date)
            if extracted_values == 0:
                missing_value_dates.append(day_date)

        self.csv_file.close()
        print(f"Collected {extracted_values} values from {starting_date.year} to {last_year}")
        print(f"There are {len(missing_value_dates)} missing values from {starting_date.year} to {last_year}.\n "
              f"They are {len(missing_value_dates)/(extracted_values+len(missing_value_dates))*100} % of the "
              f"total values.\nThe dates are: {missing_value_dates}")

        return 1



if __name__ == "__main__":
    arpav_scraper = ArpavArchiveScraper()
    starting_date = datetime.datetime(2011, 1, 1)
    arpav_archives_dir = f'/home/lorenzo/Workspace/ARPAV_archives'
    fieldnames = ['cell_value', 'pollutant', 'meas_info', 'meas_unit', 'station_name', 'city_name', 'date']
    data_archive = DataArchive(fieldnames=fieldnames, arpav_archives_dir=arpav_archives_dir)
    data_archive.scrape_and_archive_data_by_year(starting_date=starting_date, last_year=2020)

    # csv_file, writer = None, None
    # for day_id in range(365*(2020-2011)):
    #     day_date = starting_date + datetime.timedelta(days=day_id)
    #     arpav_file_dir = os.path.join(arpav_archives_dir,
    #                                   f'{day_date.year}/{day_date.month}',
    #                                   f'{day_date.year}_{day_date.month}_arpav_data.csv')
    #     if not os.path.exists(arpav_file_dir):
    #         _prepare_the_file
    #     if writer is None:
    #         # The file is already there. Delete it first
    #         print(f"ERROR: There is already a file named: {arpav_file_dir}. Delete it and restart the script.")
    #     arpav_scraper.retrieve_single_data_from_website(writer=writer,
    #                                                     city_name="Belluno",
    #                                                     date=day_date)
