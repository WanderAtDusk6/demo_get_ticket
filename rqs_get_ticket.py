import os
import re
import time
import datetime
import copy
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from lxml import etree
# pip install pandas
# pip install beautifulsoup4


class RequestSunWing:
    def __init__(self):
        self.headers = self._custom_headers()
        self.my_proxies = self._my_proxies()

    def _custom_headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
            "Accept-Encoding": "gzip, deflate, br",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }
        return headers

    def _my_proxies(self):
        proxies = {
            'http': "http://10.144.1.10:8080",
            'https': "http://10.144.1.10:8080"
        }
        return proxies

    def new_session(self):
        s = requests.Session()
        s.headers.update(self.headers)
        # s.proxies.update(self.my_proxies)
        return s

    def get_available_address_and_code(self, session, output_excel="available_addr.xlsx"):
        r = session.get(
            "https://services.sunwinggroup.ca/beta/api/search/getGatewayforBrand/en/SWG/RE",
            timeout=20,
        )
        airport_code_name_l = r.json()
        df = pd.DataFrame(airport_code_name_l)
        df.to_excel(output_excel)

    def query_url_generator(self, departure, destination, date_start,
                                num_adult="1", num_child="0"
                                ):
        """
        :param departure: 出发地代码， 例如： 'YYZ'
        :param destination: 目的地代码， 例如： 'MIA'
        :param date_start: 出发日期， 例如： '20221218'
        另外，searchtype=OW 是网页上单程的意思（ One way）
             searchtype=RE 往返查询 （Return trip）

        :return: url
        """
        url = "https://book.sunwing.ca/cgi-bin/results.cgi?" \
              "engines=S" \
              "&flex=Y" \
              "&isMobile=false" \
              "&searchtype=OW" \
              "&language=en" \
              "&code_ag=rds" \
              "&alias=btd" \
              "&date_dep={date_start}" \
              "&gateway_dep={code_start_addr}" \
              "&dest_dep={code_end_addr}" \
              "&nb_adult=1" \
              "&nb_child=0".format(
            code_start_addr=departure,
            code_end_addr=destination,
            date_start=date_start,
        )
        return url

    def get_available_date_info(self, response,):
        """
        第一次搜索时，获得有航班的日期
        :return:
        """
        # r = session.get(
        #     "https://book.sunwing.ca/cgi-bin/results.cgi?"
        #     "engines=S"
        #     "&flex=Y"
        #     "&isMobile=false"
        #     "&searchtype=OW"
        #     "&language=en"
        #     "&code_ag=rds"
        #     "&alias=btd"
        #     "&date_dep=20221017"
        #     "&gateway_dep=YYZ"
        #     "&dest_dep=MIA"
        #     "&nb_adult=1"
        #     "&nb_child=0",
        #     timeout=20,
        # )
        # # print(r.text)
        r = response
        soup = BeautifulSoup(r.text, 'html.parser')
        # todo: 加入 if, 有票无票的处理
        bs4_result_set = soup.find_all('div', class_='noresult-content')
        tag_no_result = bs4_result_set[0]
        pattern = re.compile(r"(?:date_dep)(\d+)")
        have_result_date_l = list(tag_no_result.find_all("label", attrs={"for": pattern}))

        date_l = []
        for item in have_result_date_l:
            result_date = item.attrs["for"]  # 'date_dep20221218'
            date = re.search(pattern, result_date).group(1)
            date_l.append(date)
        return date_l

    def parse_required_info(self, response, data_known={}):
        """
        :return: list

        出发到达时间： 年月日时分
        航班号：
        剩余座位数：
        飞机机型：
        票价类型：
        票价价格：
        承运航司：
        """
        # soup = BeautifulSoup(r.text, 'html.parser')
        # soup.find_all('tr', attrs={"role": "row"})
        # //*[@id="content"]/div/section/form/div/div/table/tbody/tr
        _tree = etree.HTML(response.text)
        element_row_list = _tree.xpath(
            '//*[@id="content"]/div/section/form/div/div/table[@class="fn_enable_condition_container"]/tbody/tr'
        )
        # etree.tostring(selector_list[0],encoding="utf-8")
        l = []

        for element_row in element_row_list:
            record_dict = data_known
            element_row_str = etree.tostring(element_row)
            _tree_ele_row = etree.HTML(element_row_str)
            # todo: 封装 TicketParser类类方法
            xpath_airline_info = '//td[@class="flighttable-airline"]'
            airline_info_airline = _tree_ele_row.xpath(f'{xpath_airline_info}//div[@class="haspopover"]/a')[0].text
            record_dict["航班号"] = airline_info_airline
            airline_info_detail = _tree_ele_row.xpath(f'{xpath_airline_info}//div[contains(@id,"package")]/ul/li/text()')
            airline_info_detail = [ str(_s) for _s in airline_info_detail ]
            record_dict["承运航司 飞机机型"] = airline_info_detail  # todo:

            # 日期信息已知这次不写
            xpath_date_info ='//td[@class="flighttable-itinerary"]'
            # xpath_ = '//td[@class="flighttable-itinerary-date"]'
            # time_start = _tree_ele_row.xpath(f'{xpath_date_info}//td[@class="flighttable-itinerary-departtimne"]')
            # etree.tostring(_tree_ele_row.xpath(f'{xpath_date_info}//td[@class="flighttable-itinerary-departtimne"]')[0])
            # todo: 现处理太模糊，往子节点找
            date_info_start_str = str(_tree_ele_row.xpath(f'{xpath_date_info}//td[@class="flighttable-itinerary-departtimne"]/text()'))
            date_info_time_start = re.search(
                r'\d*:\d* [ap]m', date_info_start_str
            ).group()
            record_dict["出发时间"] = date_info_time_start

            date_info_end_str = str(
                _tree_ele_row.xpath(f'{xpath_date_info}//td[@class="flighttable-itinerary-arrivetimne"]/text()'))
            date_info_end_str = date_info_end_str.replace("'", "")
            date_info_end_str = re.search(
                r'\d*:\d* [ap]m.*[(Mon)|(Tue)|(Wed)|(Thu)|(Fri)|(Sat)|(Sun)]', date_info_end_str,flags=re.I
            ).group()
            record_dict["到达时间"] = date_info_end_str

            #####
            # ticket price
            xpath_price_info = '//td[@class="flighttable-prices"]'
            price_info_l = _tree_ele_row.xpath(f'{xpath_price_info}//td[@role="gridcell"]//span/text()')
            record_dict["price"] = price_info_l

            print(record_dict)
            l.append(copy.deepcopy(record_dict))
        return l


def _my_pc_config(session, ):
    proxies = {'http': None, 'https': None}
    proxies = {
        'http': "http://10.144.1.10:8080",
        'https': "http://10.144.1.10:8080"
    }
    session.proxies.update(proxies)
    # test web
    r = session.get(
        url="https://www.baidu.com/",
        timeout=60,
    )
    print("web is ok")
    return session

def test_connect(session):
    r0 = session.get(
        url="https://www.sunwing.ca/",
        timeout=60,
    )
    r0 = session.get(
        "https://www.sunwing.ca/en/promotion/flights/cheap-flights",
        timeout=20,
    )
    return session

if __name__ == '__main__':
    r_sw_obj = RequestSunWing()
    session = r_sw_obj.new_session()
    # session.trust_env = False
    # session = _my_pc_config(session, )
    session = test_connect(session)
    ######### 单次查询方法
    # url_query = r_sw_obj.query_url_generator("YYZ", "MIA", "20221218")
    # r = session.get(url_query)
    # result = r_sw_obj.parse_required_info(r)
    ############ start
    df_query = pd.read_excel("query_table.xlsx")
    date_today = datetime.datetime.now().strftime("%Y%m%d")
    date_today = "20221020"
    result_list = []
    for i in range(df_query.shape[0]):
        addr_from = df_query.iat[i, 0]
        addr_to = df_query.iat[i, 1]
        date_fake = date_today
        print(f"###### {addr_from},{addr_to}")

        try:
            query_url_0 = r_sw_obj.query_url_generator(
                departure=addr_from,
                destination=addr_to,
                date_start=date_fake,
                num_adult="1", num_child="0"
            )
            r0 = session.get(query_url_0, timeout=20)
            date_l_have_result = r_sw_obj.get_available_date_info(r0)

            for date in date_l_have_result:
                query_url = r_sw_obj.query_url_generator(
                    departure=addr_from,
                    destination=addr_to,
                    date_start=date,
                    num_adult="1", num_child="0"
                )
                time.sleep(round(random.random(), 2)) # 随机间隔，0-1s
                r = session.get(query_url, timeout=20)
                data = {"出发地": addr_from, "目的地": addr_to, "日期": date}
                result_add = r_sw_obj.parse_required_info(r, data_known=data)

                result_list = result_list + result_add
                if (len(result_list)-1)%50==0:
                    df_output = pd.DataFrame(result_list)
                    df_output.to_excel(f"output_demo_{len(result_list)}.xlsx")
        except:
            print(f"######error:  {addr_from},{addr_to}")
            df_output = pd.DataFrame(result_list)
            df_output.to_excel("output_demo.xlsx")
    print("### done")
    df_output = pd.DataFrame(result_list)
    df_output.to_excel("output_demo.xlsx")
    print("done")