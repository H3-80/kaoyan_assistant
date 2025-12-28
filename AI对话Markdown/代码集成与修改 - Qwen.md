```
1import time
2import pandas as pd
3import mysql.connector
4from mysql.connector import Error
5from selenium import webdriver
6from selenium.webdriver.common.by import By
7from selenium.webdriver.edge.service import Service
8from selenium.webdriver.edge.options import Options
9from selenium.webdriver.support.ui import WebDriverWait
10from selenium.webdriver.support import expected_conditions as EC
11from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException, \
12    StaleElementReferenceException, InvalidSessionIdException, WebDriverException
13from selenium.webdriver.common.action_chains import ActionChains
14from selenium.webdriver.common.keys import Keys
15import logging
16import re
17import random
18import sys
19import os
20from datetime import datetime
21import threading
22from concurrent.futures import ThreadPoolExecutor, as_completed
23from queue import Queue
24import json
25import requests
26from bs4 import BeautifulSoup
27import pandas as pd
28import json
29import time
30import random
31import logging
32from datetime import datetime
33import sys
34import os
35import re
36from selenium import webdriver
37from selenium.webdriver.common.by import By
38from selenium.webdriver.support.ui import WebDriverWait
39from selenium.webdriver.support import expected_conditions as EC
40from selenium.webdriver.edge.options import Options as EdgeOptions
41from selenium.webdriver.edge.service import Service as EdgeService
42from selenium.webdriver.common.keys import Keys
43from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
44import streamlit as st
45
46# 设置页面配置 - 必须在最前面！
47st.set_page_config(
48    page_title="考研AI问答系统",
49    page_icon="🎓",
50    layout="wide",
51    initial_sidebar_state="expanded"
52)
53
54import pymysql
55from pymysql import Error
56from pymysql.cursors import DictCursor
57
58# 配置日志
59logging.basicConfig(
60    level=logging.INFO,
61    format='%(asctime)s - %(levelname)s - %(message)s',
62    handlers=[
63        logging.FileHandler(f'crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
64        logging.StreamHandler(sys.stdout)
65    ]
66)
67
68# 设置控制台编码为UTF-8
69if sys.stdout.encoding != 'utf-8':
70    try:
71        sys.stdout.reconfigure(encoding='utf-8')
72    except AttributeError:
73        import codecs
74
75        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
76
77
78class ThreadSafeSpider:
79    """线程安全的爬虫类，每个线程有自己的浏览器实例"""
80
81    def __init__(self, db_config, thread_id=0):
82        self.db_config = db_config
83        self.thread_id = thread_id
84        self.retry_count = 0
85        self.max_retries = 3  # 增加重试次数
86        self.setup_driver()
87
88    def setup_driver(self):
89        """配置Edge浏览器驱动"""
90        edge_options = Options()
91
92        # 基本设置
93        edge_options.add_argument('--no-sandbox')
94        edge_options.add_argument('--disable-dev-shm-usage')
95        edge_options.add_argument('--window-size=1920,1080')
96        edge_options.add_argument('--disable-gpu')
97        edge_options.add_argument('--disable-extensions')
98        edge_options.add_argument('--disable-background-timer-throttling')
99        edge_options.add_argument('--disable-backgrounding-occluded-windows')
100        edge_options.add_argument('--disable-renderer-backgrounding')
101        edge_options.add_argument('--no-first-run')
102        edge_options.add_argument('--no-default-browser-check')
103
104        # 性能优化设置
105        edge_options.add_argument('--disable-blink-features=AutomationControlled')
106        edge_options.add_argument('--disable-features=VizDisplayCompositor')
107        edge_options.add_argument('--disable-software-rasterizer')
108        edge_options.add_argument('--disable-dev-shm-usage')
109        edge_options.add_argument('--disable-web-security')
110        edge_options.add_argument('--disable-site-isolation-trials')
111
112        # 禁用图片和JavaScript（可选，可显著提高速度）
113        prefs = {
114            'profile.default_content_setting_values': {
115                'images': 2,  # 禁用图片
116                'javascript': 1,  # 启用JavaScript（研招网需要）
117            }
118        }
119        edge_options.add_experimental_option('prefs', prefs)
120
121        # 反检测设置
122        edge_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
123        edge_options.add_experimental_option('useAutomationExtension', False)
124        edge_options.add_argument(
125            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0')
126
127        try:
128            driver_path = r'D:\work and study\person\数据库\爬虫+数据库\kaoyan_assistant\msedgedriver.exe'
129            service = Service(driver_path)  # 指定驱动路径
130            self.driver = webdriver.Edge(service=service, options=edge_options)
131            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
132
133            # 增加超时时间
134            self.driver.set_page_load_timeout(35)  # 从30秒增加到60秒
135            self.driver.set_script_timeout(35)
136
137            # 设置隐式等待时间
138            self.driver.implicitly_wait(7)
139
140            self.wait = WebDriverWait(self.driver, 10)  # 从10秒增加到20秒
141            logging.info(f"线程 {self.thread_id} 浏览器驱动初始化成功")
142        except Exception as e:
143            logging.error(f"线程 {self.thread_id} 浏览器驱动初始化失败: {e}")
144            raise
145
146    def restart_driver(self):
147        """重启浏览器驱动"""
148        try:
149            if hasattr(self, 'driver'):
150                self.driver.quit()
151        except:
152            pass
153
154        time.sleep(5)  # 增加重启等待时间
155        self.setup_driver()
156        self.retry_count += 1
157        logging.info(f"线程 {self.thread_id} 浏览器驱动已重启，重试次数: {self.retry_count}")
158
159    def safe_execute(self, func, *args, **kwargs):
160        """安全执行函数，如果会话失效则重启浏览器"""
161        try:
162            return func(*args, **kwargs)
163        except (InvalidSessionIdException, WebDriverException, TimeoutException) as e:
164            if self.retry_count < self.max_retries:
165                logging.warning(f"线程 {self.thread_id} 浏览器会话失效或超时，准备重启: {e}")
166                self.restart_driver()
167                time.sleep(3)  # 重启后等待
168                return self.safe_execute(func, *args, **kwargs)
169            else:
170                logging.error(f"线程 {self.thread_id} 达到最大重试次数，放弃操作")
171                raise
172        except Exception as e:
173            logging.error(f"线程 {self.thread_id} 执行函数时出错: {e}")
174            raise
175
176    def get_db_connection(self):
177        """获取数据库连接"""
178        try:
179            connection = mysql.connector.connect(**self.db_config)
180            return connection
181        except Error as e:
182            logging.error(f"线程 {self.thread_id} 数据库连接失败: {e}")
183            return None
184
185    def wait_for_element(self, by, value, timeout=10):  # 增加超时时间
186        """等待元素出现"""
187        try:
188            element = WebDriverWait(self.driver, timeout).until(
189                EC.presence_of_element_located((by, value))
190            )
191            return element
192        except TimeoutException:
193            return None
194
195    def wait_for_element_clickable(self, by, value, timeout=10):  # 增加超时时间
196        """等待元素可点击"""
197        try:
198            element = WebDriverWait(self.driver, timeout).until(
199                EC.element_to_be_clickable((by, value))
200            )
201            return element
202        except TimeoutException:
203            return None
204
205    def crawl_school_majors(self, school_name, major_link=None, region=None, school_features=None,
206                            search_type='region'):
207        """爬取学校专业信息"""
208        return self.safe_execute(self._crawl_school_majors_impl, school_name, major_link, region, school_features,
209                                 search_type)
210
211    def _crawl_school_majors_impl(self, school_name, major_link=None, region=None, school_features=None,
212                                  search_type='region'):
213        """爬取学校专业信息的实现"""
214        all_majors_data = []
215
216        # 限制关键词数量以提高稳定性
217        search_keywords = [
218            "计算机", "软件工程", "人工智能", "网络空间安全", "数据科学与大数据技术",
219            "信息安全", "数学", "统计学", "医学", "药学", "护理学"
220        ]
221
222        try:
223            logging.info(f"线程 {self.thread_id} 开始爬取 {school_name} 的专业信息")
224
225            if major_link:
226                self.driver.get(major_link)
227                time.sleep(3)  # 增加等待时间
228                current_url = self.driver.current_url
229                if "/zsml/dwzy.do" not in current_url:
230                    logging.error(f"线程 {self.thread_id} 未能进入专业页面，当前URL: {current_url}")
231                    return []
232            else:
233                self.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
234                time.sleep(3)  # 增加等待时间
235
236                school_search_input = self.wait_for_element(
237                    By.CSS_SELECTOR, "input[placeholder='请输入招生单位名称']"
238                )
239                if not school_search_input:
240                    logging.error(f"线程 {self.thread_id} 未找到学校搜索框")
241                    return []
242
243                school_search_input.clear()
244                school_search_input.send_keys(school_name)
245                time.sleep(3)
246
247                search_button = self.wait_for_element_clickable(
248                    By.CSS_SELECTOR, "button.ivu-btn-primary"
249                )
250                if search_button:
251                    search_button.click()
252                    time.sleep(3)  # 增加等待时间
253                else:
254                    logging.error(f"线程 {self.thread_id} 未找到查询按钮")
255                    return []
256
257                if self.check_no_results():
258                    logging.warning(f"线程 {self.thread_id} 未找到学校: {school_name}")
259                    return []
260
261                # 在学校搜索模式下，提取地区信息和院校特性
262                if search_type == 'school':
263                    region = self.extract_region_from_school_page()
264                    if not school_features:
265                        school_features = self.extract_school_features_from_page()
266                    logging.info(f"线程 {self.thread_id} 学校 {school_name} 位于 {region}，院校特性: {school_features}")
267
268                major_button = self.find_major_button()
269                if major_button:
270                    try:
271                        button_href = major_button.get_attribute("href")
272                        if button_href and "http" in button_href:
273                            self.driver.get(button_href)
274                            time.sleep(3)  # 增加等待时间
275                    except Exception as e:
276                        logging.error(f"线程 {self.thread_id} 进入专业页面失败: {e}")
277                        return []
278                else:
279                    logging.error(f"线程 {self.thread_id} 未找到开设专业按钮")
280                    return []
281
282            current_url = self.driver.current_url
283            if "/zsml/dwzy.do" not in current_url:
284                logging.error(f"线程 {self.thread_id} 不在专业页面，无法继续")
285                return []
286
287            original_url = self.driver.current_url
288
289            for keyword in search_keywords:
290                logging.info(f"线程 {self.thread_id} 搜索关键词: {keyword}")
291                try:
292                    keyword_data = self.search_and_parse_majors(keyword, school_name, original_url, region,
293                                                                school_features,
294                                                                search_type)
295                    if keyword_data:
296                        all_majors_data.extend(keyword_data)
297                    time.sleep(2)  # 增加关键词间等待时间
298                except Exception as e:
299                    logging.error(f"线程 {self.thread_id} 搜索关键词 {keyword} 时出错: {e}")
300                    continue
301
302            # 去重处理
303            unique_majors = {}
304            for data in all_majors_data:
305                key = f"{data['school_name']}_{data['major_name']}_{data.get('major_code', '')}_{data.get('department', '')}_{data.get('research_direction', '')}"
306                if key not in unique_majors:
307                    unique_majors[key] = data
308
309            all_majors_data = list(unique_majors.values())
310            logging.info(f"线程 {self.thread_id} 去重后共获取 {len(all_majors_data)} 个唯一专业")
311
312        except Exception as e:
313            logging.error(f"线程 {self.thread_id} 爬取学校 {school_name} 失败: {e}")
314
315        return all_majors_data
316
317    def search_and_parse_majors(self, keyword, school_name, original_url, region, school_features, search_type):
318        """搜索并解析专业信息"""
319        return self.safe_execute(self._search_and_parse_majors_impl, keyword, school_name, original_url, region,
320                                 school_features, search_type)
321
322    def _search_and_parse_majors_impl(self, keyword, school_name, original_url, region, school_features, search_type):
323        """搜索并解析专业信息的实现"""
324        majors_data = []
325
326        try:
327            search_input = self.wait_for_element(
328                By.CSS_SELECTOR, "input.ivu-input.ivu-input-default[placeholder='请输入专业名称']"
329            )
330            if not search_input:
331                return []
332
333            search_input.clear()
334            search_input.send_keys(keyword)
335            time.sleep(3)
336
337            try:
338                dropdown = WebDriverWait(self.driver, 10).until(  # 增加等待时间
339                    EC.presence_of_element_located((By.CSS_SELECTOR, ".ivu-select-dropdown"))
340                )
341
342                options = dropdown.find_elements(By.CSS_SELECTOR, ".ivu-select-item")
343
344                # 修改：移除选项数量限制，处理所有选项
345                logging.info(f"线程 {self.thread_id} 关键词 '{keyword}' 找到 {len(options)} 个选项，将处理所有选项")
346
347                for i in range(len(options)):
348                    try:
349                        search_input = self.wait_for_element(
350                            By.CSS_SELECTOR, "input.ivu-input.ivu-input-default[placeholder='请输入专业名称']"
351                        )
352                        if not search_input:
353                            continue
354
355                        search_input.clear()
356                        search_input.send_keys(keyword)
357                        time.sleep(3)
358
359                        dropdown = WebDriverWait(self.driver, 10).until(  # 增加等待时间
360                            EC.presence_of_element_located((By.CSS_SELECTOR, ".ivu-select-dropdown"))
361                        )
362
363                        current_options = dropdown.find_elements(By.CSS_SELECTOR, ".ivu-select-item")
364                        if i < len(current_options):
365                            current_option = current_options[i]
366                            option_text = current_option.text.strip()
367
368                            logging.info(f"线程 {self.thread_id} 处理选项 {i + 1}/{len(options)}: {option_text}")
369
370                            self.driver.execute_script("arguments[0].click();", current_option)
371                            time.sleep(3)  # 增加等待时间
372
373                            page_data = self.parse_current_page_majors(school_name, keyword, option_text, region,
374                                                                       school_features, search_type)
375                            if page_data:
376                                majors_data.extend(page_data)
377                                logging.info(
378                                    f"线程 {self.thread_id} 选项 '{option_text}' 获取到 {len(page_data)} 条数据")
379
380                            self.driver.get(original_url)
381                            time.sleep(3)  # 增加等待时间
382
383                    except StaleElementReferenceException:
384                        logging.warning(f"线程 {self.thread_id} 选项 {i} 元素失效，跳过")
385                        continue
386                    except Exception as e:
387                        logging.error(f"线程 {self.thread_id} 处理选项 {i} 时出错: {e}")
388                        try:
389                            self.driver.get(original_url)
390                            time.sleep(3)
391                        except:
392                            pass
393                        continue
394
395            except TimeoutException:
396                # 如果没有下拉选项，直接搜索
397                logging.info(f"线程 {self.thread_id} 关键词 '{keyword}' 没有下拉选项，直接搜索")
398                search_button = self.wait_for_element_clickable(
399                    By.CSS_SELECTOR, "button.ivu-btn-primary"
400                )
401                if search_button:
402                    search_button.click()
403                    time.sleep(3)  # 增加等待时间
404
405                    page_data = self.parse_current_page_majors(school_name, keyword, keyword, region,
406                                                               school_features, search_type)
407                    if page_data:
408                        majors_data.extend(page_data)
409                        logging.info(f"线程 {self.thread_id} 直接搜索获取到 {len(page_data)} 条数据")
410
411                    self.driver.get(original_url)
412                    time.sleep(3)  # 增加等待时间
413
414        except Exception as e:
415            logging.error(f"线程 {self.thread_id} 搜索专业 {keyword} 失败: {e}")
416
417        logging.info(f"线程 {self.thread_id} 关键词 '{keyword}' 共获取 {len(majors_data)} 条数据")
418        return majors_data
419
420    def parse_current_page_majors(self, school_name, keyword, option_text, region, school_features, search_type):
421        """解析当前页面的专业信息"""
422        return self.safe_execute(self._parse_current_page_majors_impl, school_name, keyword, option_text, region,
423                                 school_features, search_type)
424
425    def _parse_current_page_majors_impl(self, school_name, keyword, option_text, region, school_features, search_type):
426        """解析当前页面专业信息的实现"""
427        majors_data = []
428
429        try:
430            self.expand_all_major_details()
431            time.sleep(2)  # 增加等待时间
432
433            major_items = self.driver.find_elements(By.CSS_SELECTOR, ".zy-item")
434
435            # 修改：移除处理项目数量限制
436            logging.info(f"线程 {self.thread_id} 找到 {len(major_items)} 个专业项目，将处理所有项目")
437
438            for item in major_items:
439                try:
440                    major_data = self.extract_major_basic_info(item)
441                    if major_data and self.is_target_major(major_data['major_name']):
442                        detailed_data_list = self.get_all_research_directions(item, school_name)
443
444                        if detailed_data_list:
445                            for detailed_data in detailed_data_list:
446                                combined_data = major_data.copy()
447                                combined_data.update(detailed_data)
448                                combined_data.update({
449                                    'school_name': school_name,
450                                    'search_keyword': keyword,
451                                    'selected_option': option_text,
452                                    'region': region,
453                                    'school_features': ', '.join(school_features) if school_features else '',
454                                    'search_type': search_type,
455                                    'data_source': f"研招网搜索 - {school_name} - {keyword} - 选项: {option_text}"
456                                })
457                                majors_data.append(combined_data)
458                        else:
459                            detailed_data = self.get_major_details_from_detail_page(item, school_name)
460                            major_data.update(detailed_data)
461                            major_data.update({
462                                'school_name': school_name,
463                                'search_keyword': keyword,
464                                'selected_option': option_text,
465                                'region': region,
466                                'school_features': ', '.join(school_features) if school_features else '',
467                                'search_type': search_type,
468                                'data_source': f"研招网搜索 - {school_name} - {keyword} - 选项: {option_text}"
469                            })
470                            majors_data.append(major_data)
471
472                except Exception as e:
473                    logging.debug(f"线程 {self.thread_id} 处理专业项目时出错: {e}")
474                    continue
475
476        except Exception as e:
477            logging.error(f"线程 {self.thread_id} 解析页面专业失败: {e}")
478
479        logging.info(f"线程 {self.thread_id} 当前页面解析到 {len(majors_data)} 个专业")
480        return majors_data
481
482    def is_target_major(self, text):
483        """检查是否为目标专业"""
484        if not text:
485            return False
486
487        target_keywords = [
488            "计算机科学与技术", "软件工程", "人工智能", "网络空间安全", "数据科学与大数据技术",
489            "计算机应用技术", "信息安全", "物联网工程", "数字媒体技术", "云计算技术与应用",
490            "区块链工程", "计算机系统结构", "计算机软件与理论", "智能科学与技术", "网络工程",
491
492            # 数学类
493            "数学与应用数学", "信息与计算科学", "数理基础科学", "应用数学", "计算数学",
494            "概率论与数理统计", "运筹学与控制论", "基础数学", "统计学", "数据计算及应用",
495            "数学教育", "金融数学", "应用统计学", "计量经济学", "数学建模",
496
497            # 医药学类
498            "临床医学", "基础医学", "药学", "护理学", "中医学", "中药学", "口腔医学",
499            "预防医学", "公共卫生与预防医学", "医学影像学", "医学检验技术", "生物医学工程",
500            "中西医临床医学", "药学（临床药学）", "麻醉学", "儿科学", "眼视光医学",
501            "精神医学", "康复治疗学", "针灸推拿学", "制药工程", "药事管理"
502        ]
503
504        text_lower = text.lower()
505        return any(keyword in text_lower for keyword in target_keywords)
506
507    def get_all_research_directions(self, item, school_name):
508        """获取专业的所有研究方向"""
509        detailed_data_list = []
510
511        try:
512            table_rows = item.find_elements(By.CSS_SELECTOR, ".ivu-table-row")
513            logging.debug(f"线程 {self.thread_id} 找到 {len(table_rows)} 个研究方向")
514
515            for row in table_rows:
516                try:
517                    department = self.extract_text_from_row(row, [
518                        "td:nth-child(1)",
519                        ".ivu-table-column-kC7Bg7",
520                        ".ivu-table-column-gqsUra"
521                    ])
522
523                    research_direction = self.extract_text_from_row(row, [
524                        "td:nth-child(4)",
525                        ".ivu-table-column-AEYuj3",
526                        ".ivu-table-column-Mb3vDC"
527                    ])
528
529                    exam_data = self.extract_exam_subjects_from_row(row)
530                    enrollment_plan = self.extract_enrollment_plan_from_row(row)
531
532                    if not enrollment_plan or not any(exam_data.values()):
533                        detail_data = self.get_research_direction_details(row, school_name)
534                        if detail_data:
535                            if not enrollment_plan and detail_data.get('enrollment_plan'):
536                                enrollment_plan = detail_data['enrollment_plan']
537                            if not any(exam_data.values()) and any(detail_data.get(key) for key in
538                                                                   ['politics_subject', 'foreign_language_subject',
539                                                                    'business_subject1', 'business_subject2']):
540                                exam_data = {k: detail_data.get(k, v) for k, v in exam_data.items()}
541
542                    detailed_data = {
543                        'department': department,
544                        'research_direction': research_direction,
545                        'enrollment_plan': enrollment_plan,
546                        **exam_data
547                    }
548
549                    detailed_data_list.append(detailed_data)
550
551                except Exception as e:
552                    logging.debug(f"线程 {self.thread_id} 处理研究方向时出错: {e}")
553                    continue
554
555        except Exception as e:
556            logging.debug(f"线程 {self.thread_id} 获取研究方向失败: {e}")
557
558        return detailed_data_list
559
560    def get_research_direction_details(self, row, school_name):
561        """获取单个研究方向的详细信息"""
562        details = {
563            'enrollment_plan': '',
564            'politics_subject': '',
565            'foreign_language_subject': '',
566            'business_subject1': '',
567            'business_subject2': ''
568        }
569
570        try:
571            detail_links = row.find_elements(By.CSS_SELECTOR, "a[href*='/zsml/yjfxdetail']")
572            if not detail_links:
573                return details
574
575            for detail_link in detail_links:
576                try:
577                    detail_url = detail_link.get_attribute("href")
578                    if detail_url:
579                        if not detail_url.startswith('http'):
580                            detail_url = 'https://yz.chsi.com.cn' + detail_url
581
582                        original_window = self.driver.current_window_handle
583                        self.driver.execute_script("window.open(arguments[0]);", detail_url)
584                        time.sleep(4)
585
586                        new_window = [w for w in self.driver.window_handles if w != original_window][0]
587                        self.driver.switch_to.window(new_window)
588                        time.sleep(4)
589
590                        if "登录" in self.driver.title or "错误" in self.driver.title:
591                            pass
592                        else:
593                            page_details = self.parse_detail_page()
594                            details.update(page_details)
595
596                        self.driver.close()
597                        self.driver.switch_to.window(original_window)
598                        time.sleep(3)
599                        break
600
601                except Exception as e:
602                    try:
603                        self.driver.switch_to.window(original_window)
604                    except:
605                        pass
606                    continue
607
608        except Exception as e:
609            pass
610
611        return details
612
613    def extract_text_from_row(self, row, selectors):
614        """从表格行中提取文本"""
615        for selector in selectors:
616            try:
617                element = row.find_element(By.CSS_SELECTOR, selector)
618                text = element.text.strip()
619                if text:
620                    return text
621            except:
622                continue
623        return ""
624
625    def extract_exam_subjects_from_row(self, row):
626        """从表格行中提取考试科目信息"""
627        exam_data = {
628            'politics_subject': '',
629            'foreign_language_subject': '',
630            'business_subject1': '',
631            'business_subject2': ''
632        }
633
634        try:
635            exam_buttons = row.find_elements(By.CSS_SELECTOR,
636                                             "a[href*='javascript:;'], .ivu-table-column-xA7jhY a, td:nth-child(9) a")
637
638            for button in exam_buttons:
639                if "查看" in button.text:
640                    try:
641                        self.driver.execute_script("arguments[0].click();", button)
642                        time.sleep(2)
643
644                        popup = self.wait_for_element(By.CSS_SELECTOR,
645                                                      ".ivu-poptip-popper, .ivu-tooltip-popper, .kskm-modal")
646
647                        if popup:
648                            self.parse_exam_popup_content(popup, exam_data)
649                            self.close_popup()
650                            break
651
652                    except Exception as e:
653                        continue
654
655        except Exception as e:
656            pass
657
658        return exam_data
659
660    def parse_exam_popup_content(self, popup, exam_data):
661        """解析考试科目弹出窗口内容"""
662        try:
663            # 首先尝试查找kskm-item结构
664            kskm_items = popup.find_elements(By.CSS_SELECTOR, ".kskm-item")
665            if kskm_items:
666                # 取第一个考试科目组合
667                first_kskm = kskm_items[0]
668
669                # 获取科目类型和详情
670                kskm_types = first_kskm.find_elements(By.CSS_SELECTOR, ".kskm-type .item")
671                kskm_details = first_kskm.find_elements(By.CSS_SELECTOR, ".kskm-detail .item")
672
673                # 按顺序匹配科目
674                for i in range(min(len(kskm_types), len(kskm_details))):
675                    subject_type = kskm_types[i].text.strip()
676                    subject_detail = kskm_details[i].text.strip()
677
678                    # 清理详情文本
679                    clean_detail = re.sub(r'见招生简章|查看详情', '', subject_detail).strip()
680
681                    if subject_type == '政治':
682                        exam_data['politics_subject'] = clean_detail
683                    elif subject_type == '外语':
684                        exam_data['foreign_language_subject'] = clean_detail
685                    elif subject_type == '业务课一':
686                        exam_data['business_subject1'] = clean_detail
687                    elif subject_type == '业务课二':
688                        exam_data['business_subject2'] = clean_detail
689                return
690
691            # 如果没有找到kskm-item结构，尝试其他方式
692            kskm_details = popup.find_elements(By.CSS_SELECTOR, ".kskm-detail .item")
693            if kskm_details:
694                # 按顺序提取科目
695                for i, item in enumerate(kskm_details):
696                    text = item.text.strip()
697                    if not text:
698                        continue
699
700                    clean_text = re.sub(r'见招生简章|查看详情', '', text).strip()
701
702                    if i == 0:  # 第一个通常是政治
703                        exam_data['politics_subject'] = clean_text
704                    elif i == 1:  # 第二个通常是外语
705                        exam_data['foreign_language_subject'] = clean_text
706                    elif i == 2:  # 第三个通常是业务课一
707                        exam_data['business_subject1'] = clean_text
708                    elif i == 3:  # 第四个通常是业务课二
709                        exam_data['business_subject2'] = clean_text
710                return
711
712            # 最后尝试按文本解析
713            popup_text = popup.text
714            lines = [line.strip() for line in popup_text.split('\n') if line.strip()]
715
716            for i, line in enumerate(lines):
717                if i == 0 or '思想政治' in line or '(101)' in line:
718                    exam_data['politics_subject'] = line
719                elif i == 1 or any(keyword in line for keyword in
720                                   ['英语', '日语', '俄语', '德语', '法语', '(201)', '(202)', '(203)', '(204)']):
721                    exam_data['foreign_language_subject'] = line
722                elif i == 2 or '业务课一' in line or '专业课一' in line:
723                    exam_data['business_subject1'] = line
724                elif i == 3 or '业务课二' in line or '专业课二' in line:
725                    exam_data['business_subject2'] = line
726
727        except Exception as e:
728            logging.error(f"线程 {self.thread_id} 解析考试科目弹出框失败: {e}")
729
730    def extract_enrollment_plan_from_row(self, row):
731        """从表格行中提取拟招生人数"""
732        enrollment_plan = ""
733
734        try:
735            plan_buttons = row.find_elements(By.CSS_SELECTOR,
736                                             ".ivu-table-column-Ln8auZ a, .ivu-table-column-4bER4t a, td:nth-child(8) a")
737
738            for button in plan_buttons:
739                if "查看" in button.text:
740                    try:
741                        self.driver.execute_script("arguments[0].click();", button)
742                        time.sleep(4)
743
744                        popup = self.wait_for_element(By.CSS_SELECTOR,
745                                                      ".ivu-tooltip-popper, .ivu-poptip-popper")
746
747                        if popup:
748                            plan_text = popup.text.strip()
749
750                            match = re.search(r'专业：\s*(\d+)', plan_text)
751                            if match:
752                                enrollment_plan = f"{match.group(1)}(不含推免)"
753                            else:
754                                match = re.search(r'(\d+)\s*\(不含推免\)', plan_text)
755                                if match:
756                                    enrollment_plan = f"{match.group(1)}(不含推免)"
757                                else:
758                                    match = re.search(r'(\d+)', plan_text)
759                                    if match:
760                                        enrollment_plan = f"{match.group(1)}(不含推免)"
761                                    else:
762                                        enrollment_plan = plan_text
763
764                            self.close_popup()
765                            break
766
767                    except Exception as e:
768                        continue
769
770        except Exception as e:
771            pass
772
773        return enrollment_plan
774
775    def close_popup(self):
776        """关闭弹出窗口"""
777        try:
778            body = self.driver.find_element(By.TAG_NAME, "body")
779            body.click()
780            time.sleep(2)
781        except:
782            pass
783
784    def extract_major_basic_info(self, item):
785        """提取专业基本信息"""
786        try:
787            name_elem = item.find_element(By.CSS_SELECTOR, ".zy-name")
788            name_text = name_elem.text.strip()
789
790            if not name_text:
791                return None
792
793            code_match = re.search(r'\((\d+)\)', name_text)
794            major_code = code_match.group(1) if code_match else ""
795            major_name = re.sub(r'\(\d+\)', '', name_text).strip()
796
797            if not major_name:
798                return None
799
800            degree_type = ""
801            try:
802                # 提取学位类型 - 学术学位或专业学位
803                degree_elem = item.find_element(By.CSS_SELECTOR, ".zy-tag.xs, .zy-tag.zs")
804                degree_type = degree_elem.text.strip()
805            except:
806                # 如果找不到明确的学位标签，尝试从专业名称判断
807                if "专业学位" in name_text:
808                    degree_type = "专业学位"
809                elif "学术学位" in name_text:
810                    degree_type = "学术学位"
811                else:
812                    # 根据专业代码判断（085开头通常是专业学位）
813                    if major_code and major_code.startswith('085'):
814                        degree_type = "专业学位"
815                    else:
816                        degree_type = "学术学位"
817
818            return {
819                'major_name': major_name,
820                'major_code': major_code,
821                'degree_type': degree_type
822            }
823
824        except Exception as e:
825            return None
826
827    def get_major_details_from_detail_page(self, item, school_name):
828        """从详情页面获取专业详细信息"""
829        details = {
830            'enrollment_plan': '',
831            'politics_subject': '',
832            'foreign_language_subject': '',
833            'business_subject1': '',
834            'business_subject2': ''
835        }
836
837        try:
838            detail_links = item.find_elements(By.CSS_SELECTOR,
839                                              "a[href*='/zsml/queryYjfx'], a[href*='/zsml/yjfxdetail']")
840
841            if detail_links:
842                for detail_link in detail_links:
843                    try:
844                        detail_url = detail_link.get_attribute("href")
845                        if detail_url:
846                            if not detail_url.startswith('http'):
847                                detail_url = 'https://yz.chsi.com.cn' + detail_url
848
849                            original_window = self.driver.current_window_handle
850                            self.driver.execute_script("window.open(arguments[0]);", detail_url)
851                            time.sleep(4)
852
853                            new_window = [w for w in self.driver.window_handles if w != original_window][0]
854                            self.driver.switch_to.window(new_window)
855                            time.sleep(4)
856
857                            if "登录" in self.driver.title or "错误" in self.driver.title:
858                                pass
859                            else:
860                                page_details = self.parse_detail_page()
861                                details.update(page_details)
862
863                            self.driver.close()
864                            self.driver.switch_to.window(original_window)
865                            time.sleep(3)
866                            break
867
868                    except Exception as e:
869                        try:
870                            self.driver.switch_to.window(original_window)
871                        except:
872                            pass
873                        continue
874
875        except Exception as e:
876            pass
877
878        return details
879
880    def parse_detail_page(self):
881        """解析详情页面"""
882        details = {
883            'enrollment_plan': '',
884            'politics_subject': '',
885            'foreign_language_subject': '',
886            'business_subject1': '',
887            'business_subject2': ''
888        }
889
890        try:
891            time.sleep(4)
892
893            enrollment_plan = self.extract_enrollment_plan_from_detail_page()
894            if enrollment_plan:
895                details['enrollment_plan'] = enrollment_plan
896
897            exam_data = self.extract_exam_subjects_from_detail_page()
898            details.update(exam_data)
899
900        except Exception as e:
901            logging.error(f"线程 {self.thread_id} 解析详情页面失败: {e}")
902
903        return details
904
905    def extract_enrollment_plan_from_detail_page(self):
906        """从详情页面提取拟招生人数"""
907        enrollment_plan = ""
908
909        try:
910            selectors = [
911                "//div[contains(@class, 'item') and contains(., '拟招生人数')]//div[contains(@class, 'value')]",
912                "//div[contains(text(), '拟招生人数：')]/following-sibling::div",
913                "//*[contains(text(), '专业：')]",
914                ".enrollment-plan",
915                ".value"
916            ]
917
918            for selector in selectors:
919                try:
920                    if selector.startswith("//"):
921                        elements = self.driver.find_elements(By.XPATH, selector)
922                    else:
923                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
924
925                    for element in elements:
926                        text = element.text.strip()
927                        if "专业：" in text:
928                            match = re.search(r'专业：\s*(\d+)', text)
929                            if match:
930                                enrollment_plan = f"{match.group(1)}(不含推免)"
931                                break
932                        elif text and re.search(r'\d+', text):
933                            match = re.search(r'(\d+)', text)
934                            if match:
935                                enrollment_plan = f"{match.group(1)}(不含推免)"
936                                break
937
938                    if enrollment_plan:
939                        break
940                except:
941                    continue
942
943            if not enrollment_plan:
944                page_text = self.driver.page_source
945                match = re.search(r'专业：\s*(\d+)', page_text)
946                if match:
947                    enrollment_plan = f"{match.group(1)}(不含推免)"
948
949        except Exception as e:
950            pass
951
952        return enrollment_plan
953
954    def extract_exam_subjects_from_detail_page(self):
955        """从详情页面提取考试科目信息"""
956        exam_data = {
957            'politics_subject': '',
958            'foreign_language_subject': '',
959            'business_subject1': '',
960            'business_subject2': ''
961        }
962
963        try:
964            # 首先查找kskm-detail-list结构
965            kskm_lists = self.driver.find_elements(By.CSS_SELECTOR, ".kskm-detail-list")
966            for kskm_list in kskm_lists:
967                kskm_items = kskm_list.find_elements(By.CSS_SELECTOR, ".kskm-item")
968                if kskm_items:
969                    # 取第一个考试科目组合
970                    first_kskm = kskm_items[0]
971
972                    # 获取科目类型和详情
973                    kskm_types = first_kskm.find_elements(By.CSS_SELECTOR, ".kskm-type .item")
974                    kskm_details = first_kskm.find_elements(By.CSS_SELECTOR, ".kskm-detail .item")
975
976                    # 按顺序匹配科目
977                    for i in range(min(len(kskm_types), len(kskm_details))):
978                        subject_type = kskm_types[i].text.strip()
979                        subject_detail = kskm_details[i].text.strip()
980
981                        # 清理详情文本
982                        clean_detail = re.sub(r'见招生简章|查看详情', '', subject_detail).strip()
983
984                        if subject_type == '政治':
985                            exam_data['politics_subject'] = clean_detail
986                        elif subject_type == '外语':
987                            exam_data['foreign_language_subject'] = clean_detail
988                        elif subject_type == '业务课一':
989                            exam_data['business_subject1'] = clean_detail
990                        elif subject_type == '业务课二':
991                            exam_data['business_subject2'] = clean_detail
992                    break
993
994            # 如果没有找到kskm-detail-list，尝试其他选择器
995            if not any(exam_data.values()):
996                kskm_selectors = [
997                    ".kskm-item",
998                    ".exam-subjects",
999                    "[class*='kskm']"
1000                ]
1001
1002                for selector in kskm_selectors:
1003                    try:
1004                        kskm_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
1005                        if kskm_elements:
1006                            for element in kskm_elements:
1007                                text = element.text
1008                                lines = text.split('\n')
1009
1010                                for i, line in enumerate(lines):
1011                                    line = line.strip()
1012                                    if not line:
1013                                        continue
1014
1015                                    if i == 0 or '思想政治' in line or '(101)' in line:
1016                                        exam_data['politics_subject'] = line
1017                                    elif i == 1 or any(keyword in line for keyword in
1018                                                       ['英语', '日语', '俄语', '德语', '法语', '(201)', '(202)',
1019                                                        '(203)',
1020                                                        '(204)']):
1021                                        exam_data['foreign_language_subject'] = line
1022                                    elif i == 2 or '业务课一' in line or '专业课一' in line:
1023                                        exam_data['business_subject1'] = line
1024                                    elif i == 3 or '业务课二' in line or '专业课二' in line:
1025                                        exam_data['business_subject2'] = line
1026
1027                            if any(exam_data.values()):
1028                                break
1029                    except:
1030                        continue
1031
1032        except Exception as e:
1033            logging.error(f"线程 {self.thread_id} 提取考试科目失败: {e}")
1034
1035        return exam_data
1036
1037    def extract_region_from_school_page(self):
1038        """从学校页面提取地区信息"""
1039        try:
1040            region_selectors = [
1041                ".yx-area",
1042                ".yx-detail-info .yx-area",
1043                "//div[contains(@class, 'yx-area')]",
1044                "//div[contains(text(), '湖北') or contains(text(), '北京') or contains(text(), '上海') or contains(text(), '天津') or contains(text(), '重庆') or contains(text(), '河北') or contains(text(), '山西') or contains(text(), '辽宁') or contains(text(), '吉林') or contains(text(), '黑龙江') or contains(text(), '江苏') or contains(text(), '浙江') or contains(text(), '安徽') or contains(text(), '福建') or contains(text(), '江西') or contains(text(), '山东') or contains(text(), '河南') or contains(text(), '湖北') or contains(text(), '湖南') or contains(text(), '广东') or contains(text(), '海南') or contains(text(), '四川') or contains(text(), '贵州') or contains(text(), '云南') or contains(text(), '陕西') or contains(text(), '甘肃') or contains(text(), '青海') or contains(text(), '台湾') or contains(text(), '内蒙古') or contains(text(), '广西') or contains(text(), '西藏') or contains(text(), '宁夏') or contains(text(), '新疆') or contains(text(), '香港') or contains(text(), '澳门')]"
1045            ]
1046
1047            for selector in region_selectors:
1048                try:
1049                    if selector.startswith("//"):
1050                        elements = self.driver.find_elements(By.XPATH, selector)
1051                    else:
1052                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
1053
1054                    for element in elements:
1055                        text = element.text.strip()
1056                        if text and len(text) <= 10:
1057                            clean_text = re.sub(r'[^\u4e00-\u9fa5]', '', text)
1058                            if clean_text and len(clean_text) >= 2:
1059                                logging.info(f"线程 {self.thread_id} 提取到地区信息: {clean_text}")
1060                                return clean_text
1061                except:
1062                    continue
1063
1064            page_text = self.driver.page_source
1065            region_patterns = [
1066                r'<div class="yx-area"[^>]*>.*?([\u4e00-\u9fa5]{2,10})</div>',
1067                r'所在地.*?([\u4e00-\u9fa5]{2,10})',
1068                r'地区.*?([\u4e00-\u9fa5]{2,10})'
1069            ]
1070
1071            for pattern in region_patterns:
1072                match = re.search(pattern, page_text, re.IGNORECASE)
1073                if match:
1074                    region = match.group(1)
1075                    logging.info(f"线程 {self.thread_id} 从页面源码提取到地区信息: {region}")
1076                    return region
1077
1078            return "未知"
1079        except Exception as e:
1080            logging.error(f"线程 {self.thread_id} 提取地区信息失败: {e}")
1081            return "未知"
1082
1083    def extract_school_features_from_page(self):
1084        """从学校页面提取院校特性"""
1085        try:
1086            features = []
1087            feature_selectors = [
1088                ".yx-tag",
1089                ".yx-tags .yx-tag",
1090                "//div[contains(@class, 'yx-tag')]"
1091            ]
1092
1093            for selector in feature_selectors:
1094                try:
1095                    if selector.startswith("//"):
1096                        elements = self.driver.find_elements(By.XPATH, selector)
1097                    else:
1098                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
1099
1100                    for element in elements:
1101                        text = element.text.strip()
1102                        if text and "博士点" in text:
1103                            features.append("博士点")
1104                        elif text and "双一流" in text:
1105                            features.append("双一流建设高校")
1106                        elif text and "自划线" in text:
1107                            features.append("自划线院校")
1108                        elif text and text not in features:
1109                            features.append(text)
1110                except:
1111                    continue
1112
1113            return list(set(features))
1114        except Exception as e:
1115            logging.error(f"线程 {self.thread_id} 提取院校特性失败: {e}")
1116            return []
1117
1118    def expand_all_major_details(self):
1119        """展开所有专业详细信息"""
1120        try:
1121            expand_buttons = self.driver.find_elements(By.CSS_SELECTOR,
1122                                                       ".show-more, [class*='expand'], [class*='more']")
1123            expanded_count = 0
1124
1125            for button in expand_buttons:
1126                try:
1127                    if button.is_displayed() and ("展开" in button.text or "详情" in button.text):
1128                        self.driver.execute_script("arguments[0].click();", button)
1129                        time.sleep(1)  # 增加等待时间
1130                        expanded_count += 1
1131                except:
1132                    continue
1133
1134            return expanded_count > 0
1135
1136        except Exception as e:
1137            return False
1138
1139    def find_major_button(self):
1140        """查找开设专业按钮"""
1141        button_selectors = [
1142            "a.zy-btn.ivu-btn.ivu-btn-primary",
1143            "a.zy-btn",
1144            "a[class*='zy-btn']",
1145            "//a[contains(@class, 'zy-btn')]",
1146            "//a[contains(@href, '/zsml/dwzy.do')]",
1147            "//span[contains(text(), '开设专业')]/parent::a",
1148            "//a[.//span[contains(text(), '开设专业')]]",
1149            "//a[contains(text(), '开设专业')]"
1150        ]
1151
1152        for selector in button_selectors:
1153            try:
1154                if selector.startswith("//"):
1155                    button = self.driver.find_element(By.XPATH, selector)
1156                else:
1157                    button = self.driver.find_element(By.CSS_SELECTOR, selector)
1158
1159                if button.is_displayed():
1160                    return button
1161            except:
1162                continue
1163
1164        return None
1165
1166    def check_no_results(self):
1167        """检查是否没有结果"""
1168        try:
1169            no_data_indicators = [
1170                "//*[contains(text(), '暂无数据')]",
1171                "//*[contains(text(), '没有找到')]",
1172                "//*[contains(text(), '未查询到')]",
1173                "//*[contains(text(), '无相关结果')]"
1174            ]
1175
1176            for indicator in no_data_indicators:
1177                try:
1178                    no_data = self.driver.find_element(By.XPATH, indicator)
1179                    if no_data and no_data.is_displayed():
1180                        return True
1181                except:
1182                    continue
1183            return False
1184        except:
1185            return False
1186
1187    def close(self):
1188        """关闭浏览器"""
1189        if hasattr(self, 'driver'):
1190            try:
1191                self.driver.quit()
1192                logging.info(f"线程 {self.thread_id} 浏览器已关闭")
1193            except:
1194                pass
1195
1196
1197class CompleteInfoSpider:
1198    def __init__(self, username=None, password=None, max_workers=2):  # 默认线程数改为2
1199        self.db_config = {
1200            'host': 'localhost',
1201            'user': 'root',
1202            'password': 'Wza!64416685',
1203            'database': 'kaoyan_data'
1204        }
1205
1206        self.username = username
1207        self.password = password
1208        self.is_logged_in = False
1209        self.max_workers = max_workers
1210        self.lock = threading.Lock()
1211        self.excel_filename = f'完整信息_考研专业信息-{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
1212
1213        self.check_and_create_tables()
1214        self.init_excel_file()
1215
1216    def init_excel_file(self):
1217        """初始化Excel文件"""
1218        try:
1219            df = pd.DataFrame(columns=[
1220                '学校', '专业名称', '专业代码', '院系', '研究方向',
1221                '政治科目', '外语科目', '业务课一', '业务课二',
1222                '拟招生人数', '地区', '院校特性', '学位类型',
1223                '搜索关键词', '选择选项', '数据来源'
1224            ])
1225            df.to_excel(self.excel_filename, index=False, engine='openpyxl')
1226            logging.info(f"Excel文件已初始化: {self.excel_filename}")
1227        except Exception as e:
1228            logging.error(f"初始化Excel文件失败: {e}")
1229
1230    def append_to_excel(self, data_list):
1231        """追加数据到Excel文件（线程安全）"""
1232        if not data_list:
1233            return
1234
1235        with self.lock:
1236            try:
1237                # 读取现有数据
1238                try:
1239                    existing_df = pd.read_excel(self.excel_filename, engine='openpyxl')
1240                except:
1241                    existing_df = pd.DataFrame()
1242
1243                # 创建新数据框
1244                new_data = []
1245                for data in data_list:
1246                    new_data.append({
1247                        '学校': data['school_name'],
1248                        '专业名称': data['major_name'],
1249                        '专业代码': data.get('major_code', ''),
1250                        '院系': data.get('department', ''),
1251                        '研究方向': data.get('research_direction', ''),
1252                        '政治科目': data.get('politics_subject', ''),
1253                        '外语科目': data.get('foreign_language_subject', ''),
1254                        '业务课一': data.get('business_subject1', ''),
1255                        '业务课二': data.get('business_subject2', ''),
1256                        '拟招生人数': data.get('enrollment_plan', ''),
1257                        '地区': data.get('region', ''),
1258                        '院校特性': data.get('school_features', ''),
1259                        '学位类型': data.get('degree_type', ''),
1260                        '搜索关键词': data.get('search_keyword', ''),
1261                        '选择选项': data.get('selected_option', ''),
1262                        '数据来源': data['data_source']
1263                    })
1264
1265                new_df = pd.DataFrame(new_data)
1266
1267                # 合并数据
1268                if not existing_df.empty:
1269                    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
1270                else:
1271                    combined_df = new_df
1272
1273                # 保存到文件
1274                combined_df.to_excel(self.excel_filename, index=False, engine='openpyxl')
1275                logging.info(f"已追加 {len(data_list)} 条数据到Excel文件")
1276
1277            except Exception as e:
1278                logging.error(f"追加数据到Excel失败: {e}")
1279
1280    def check_and_create_tables(self):
1281        """检查并创建表（不再删除现有表）"""
1282        connection = self.get_db_connection()
1283        if not connection:
1284            return
1285
1286        try:
1287            cursor = connection.cursor()
1288
1289            # 检查表是否存在，如果不存在则创建
1290            cursor.execute("SHOW TABLES LIKE 'crawl_progress'")
1291            if not cursor.fetchone():
1292                cursor.execute("""
1293                    CREATE TABLE IF NOT EXISTS crawl_progress (
1294                        id INT AUTO_INCREMENT PRIMARY KEY,
1295                        region VARCHAR(100),
1296                        school_name VARCHAR(255) NOT NULL,
1297                        search_type ENUM('region', 'school') DEFAULT 'region',
1298                        status ENUM('pending', 'completed', 'failed') DEFAULT 'pending',
1299                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
1300                        UNIQUE KEY unique_search_school (region, school_name, search_type)
1301                    )
1302                """)
1303                logging.info("创建表 crawl_progress")
1304
1305            cursor.execute("SHOW TABLES LIKE 'exam_subjects'")
1306            if not cursor.fetchone():
1307                cursor.execute("""
1308                    CREATE TABLE IF NOT EXISTS exam_subjects (
1309                        id INT AUTO_INCREMENT PRIMARY KEY,
1310                        school_name VARCHAR(255) NOT NULL,
1311                        major_name VARCHAR(255) NOT NULL,
1312                        major_code VARCHAR(100),
1313                        department VARCHAR(255),
1314                        research_direction VARCHAR(255),
1315                        politics_subject VARCHAR(100),
1316                        foreign_language_subject VARCHAR(100),
1317                        business_subject1 VARCHAR(255),
1318                        business_subject2 VARCHAR(255),
1319                        enrollment_plan VARCHAR(100),
1320                        exam_scope TEXT,
1321                        reference_books TEXT,
1322                        region VARCHAR(100),
1323                        data_source VARCHAR(500) NOT NULL,
1324                        school_features TEXT,
1325                        degree_type VARCHAR(50),
1326                        search_type ENUM('region', 'school') DEFAULT 'region',
1327                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
1328                        UNIQUE KEY unique_school_major_direction (school_name(100), major_name(100), major_code(50), department(100), research_direction(100))
1329                    )
1330                """)
1331                logging.info("创建表 exam_subjects")
1332
1333            connection.commit()
1334            logging.info("数据表检查完成")
1335
1336        except Error as e:
1337            logging.error(f"检查表失败: {e}")
1338            try:
1339                # 如果创建失败，尝试创建不带唯一索引的表
1340                cursor.execute("""
1341                    CREATE TABLE IF NOT EXISTS exam_subjects (
1342                        id INT AUTO_INCREMENT PRIMARY KEY,
1343                        school_name VARCHAR(255) NOT NULL,
1344                        major_name VARCHAR(255) NOT NULL,
1345                        major_code VARCHAR(100),
1346                        department VARCHAR(255),
1347                        research_direction VARCHAR(255),
1348                        politics_subject VARCHAR(100),
1349                        foreign_language_subject VARCHAR(100),
1350                        business_subject1 VARCHAR(255),
1351                        business_subject2 VARCHAR(255),
1352                        enrollment_plan VARCHAR(100),
1353                        exam_scope TEXT,
1354                        reference_books TEXT,
1355                        region VARCHAR(100),
1356                        data_source VARCHAR(500) NOT NULL,
1357                        school_features TEXT,
1358                        degree_type VARCHAR(50),
1359                        search_type ENUM('region', 'school') DEFAULT 'region',
1360                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
1361                    )
1362                """)
1363                connection.commit()
1364                logging.info("数据表创建成功（无唯一索引）")
1365            except Error as e2:
1366                logging.error(f"创建无索引表也失败: {e2}")
1367        finally:
1368            if connection.is_connected():
1369                cursor.close()
1370                connection.close()
1371
1372    def get_db_connection(self):
1373        """获取数据库连接"""
1374        try:
1375            connection = mysql.connector.connect(**self.db_config)
1376            return connection
1377        except Error as e:
1378            logging.error(f"数据库连接失败: {e}")
1379            return None
1380
1381    def check_school_exists_in_database(self, school_name, search_type='region'):
1382        """检查学校是否已在数据库中存在"""
1383        connection = self.get_db_connection()
1384        if not connection:
1385            return False
1386
1387        try:
1388            cursor = connection.cursor()
1389
1390            # 检查exam_subjects表中是否有该学校的数据
1391            query = "SELECT COUNT(*) FROM exam_subjects WHERE school_name = %s AND search_type = %s"
1392            cursor.execute(query, (school_name, search_type))
1393            count = cursor.fetchone()[0]
1394
1395            return count > 0
1396        except Error as e:
1397            logging.error(f"检查学校是否存在失败: {e}")
1398            return False
1399        finally:
1400            if connection.is_connected():
1401                cursor.close()
1402                connection.close()
1403
1404    def delete_school_data(self, school_name, search_type='region'):
1405        """删除指定学校的数据"""
1406        connection = self.get_db_connection()
1407        if not connection:
1408            return False
1409
1410        try:
1411            cursor = connection.cursor()
1412
1413            # 删除exam_subjects表中该学校的数据
1414            query = "DELETE FROM exam_subjects WHERE school_name = %s AND search_type = %s"
1415            cursor.execute(query, (school_name, search_type))
1416
1417            # 删除crawl_progress表中该学校的记录
1418            query = "DELETE FROM crawl_progress WHERE school_name = %s AND search_type = %s"
1419            cursor.execute(query, (school_name, search_type))
1420
1421            connection.commit()
1422            logging.info(f"已删除学校 {school_name} 的现有数据")
1423            return True
1424        except Error as e:
1425            logging.error(f"删除学校数据失败: {e}")
1426            connection.rollback()
1427            return False
1428        finally:
1429            if connection.is_connected():
1430                cursor.close()
1431                connection.close()
1432
1433    def ask_user_for_existing_schools(self, school_list, search_type='region'):
1434        """询问用户对已存在学校的处理方式"""
1435        schools_to_crawl = []
1436
1437        print(f"\n=== 检查已存在的学校 ===")
1438        print(f"共找到 {len(school_list)} 所学校")
1439
1440        for i, school_info in enumerate(school_list, 1):
1441            school_name = school_info['name']
1442            exists = self.check_school_exists_in_database(school_name, search_type)
1443
1444            if exists:
1445                print(f"\n{i}. 学校 '{school_name}' 已存在于数据库中")
1446                while True:
1447                    choice = input(f"是否重新爬取学校 '{school_name}'？(y/n): ").strip().lower()
1448                    if choice in ['y', 'yes', '是']:
1449                        # 用户选择重新爬取，删除现有数据
1450                        if self.delete_school_data(school_name, search_type):
1451                            schools_to_crawl.append(school_info)
1452                            print(f"学校 '{school_name}' 将重新爬取")
1453                        else:
1454                            print(f"删除学校 '{school_name}' 数据失败，将跳过该学校")
1455                        break
1456                    elif choice in ['n', 'no', '否']:
1457                        print(f"学校 '{school_name}' 将跳过")
1458                        break
1459                    else:
1460                        print("请输入 y/yes/是 或 n/no/否")
1461            else:
1462                # 学校不存在，直接加入爬取列表
1463                schools_to_crawl.append(school_info)
1464                print(f"{i}. 学校 '{school_name}' 未在数据库中找到，将进行爬取")
1465
1466        print(f"\n最终将爬取 {len(schools_to_crawl)} 所学校")
1467        return schools_to_crawl
1468
1469    def save_to_database(self, data):
1470        """保存数据到数据库"""
1471        if not data:
1472            return False
1473
1474        connection = self.get_db_connection()
1475        if not connection:
1476            return False
1477
1478        try:
1479            cursor = connection.cursor()
1480            saved_count = 0
1481
1482            cursor.execute("SHOW TABLES LIKE 'exam_subjects'")
1483            table_exists = cursor.fetchone()
1484
1485            if not table_exists:
1486                logging.error("表 exam_subjects 不存在，无法保存数据")
1487                return False
1488
1489            for item in data:
1490                try:
1491                    school_name = item.get('school_name', '')
1492                    major_name = item.get('major_name', '')
1493                    major_code = item.get('major_code', '')
1494                    department = item.get('department', '')
1495                    research_direction = item.get('research_direction', '')
1496                    politics_subject = item.get('politics_subject', '')
1497                    foreign_language_subject = item.get('foreign_language_subject', '')
1498                    business_subject1 = item.get('business_subject1', '')
1499                    business_subject2 = item.get('business_subject2', '')
1500                    enrollment_plan = item.get('enrollment_plan', '')
1501                    exam_scope = item.get('exam_scope', '')
1502                    region = item.get('region', '')
1503                    data_source = item.get('data_source', '')
1504                    school_features = item.get('school_features', '')
1505                    degree_type = item.get('degree_type', '')
1506                    search_type = item.get('search_type', 'region')
1507
1508                    query = """
1509                    INSERT IGNORE INTO exam_subjects 
1510                    (school_name, major_name, major_code, department, research_direction,
1511                     politics_subject, foreign_language_subject, business_subject1, business_subject2,
1512                     enrollment_plan, exam_scope, region, data_source, school_features, degree_type, search_type)
1513                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
1514                    """
1515                    cursor.execute(query, (
1516                        school_name,
1517                        major_name,
1518                        major_code,
1519                        department,
1520                        research_direction,
1521                        politics_subject,
1522                        foreign_language_subject,
1523                        business_subject1,
1524                        business_subject2,
1525                        enrollment_plan,
1526                        exam_scope,
1527                        region,
1528                        data_source,
1529                        school_features,
1530                        degree_type,
1531                        search_type
1532                    ))
1533                    saved_count += 1
1534
1535                except Error as e:
1536                    continue
1537
1538            connection.commit()
1539            logging.info(f"成功保存 {saved_count} 条数据到数据库")
1540            return True
1541
1542        except Error as e:
1543            logging.error(f"保存到数据库失败: {e}")
1544            connection.rollback()
1545            return False
1546        finally:
1547            if connection.is_connected():
1548                cursor.close()
1549                connection.close()
1550
1551    def crawl_school_task(self, school_info, region=None, search_type='region', thread_id=0):
1552        """单个学校的爬取任务（用于多线程）"""
1553        thread_spider = ThreadSafeSpider(self.db_config, thread_id)
1554        try:
1555            school_name = school_info['name']
1556            logging.info(f"线程 {thread_id} 开始处理: {school_name}")
1557
1558            school_data = thread_spider.crawl_school_majors(
1559                school_info['name'],
1560                school_info.get('major_link'),
1561                region,
1562                school_info.get('features', []),
1563                search_type
1564            )
1565
1566            if school_data:
1567                # 保存到数据库
1568                self.save_to_database(school_data)
1569                # 保存到Excel
1570                self.append_to_excel(school_data)
1571                logging.info(f"线程 {thread_id} 完成学校 {school_name}，获取 {len(school_data)} 条数据")
1572                return school_data
1573            else:
1574                logging.info(f"线程 {thread_id} 学校 {school_name} 没有找到目标专业")
1575                return []
1576
1577        except Exception as e:
1578            logging.error(f"线程 {thread_id} 处理学校 {school_info['name']} 时发生错误: {e}")
1579            return []
1580        finally:
1581            thread_spider.close()
1582
1583    def crawl_all_schools_multithread(self, school_list, region=None, search_type='region'):
1584        """多线程批量爬取所有学校"""
1585        all_data = []
1586
1587        logging.info(f"开始多线程爬取，共 {len(school_list)} 所学校，使用 {self.max_workers} 个线程")
1588
1589        # 使用线程池
1590        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
1591            # 提交所有任务
1592            future_to_school = {
1593                executor.submit(self.crawl_school_task, school, region, search_type, i): (school, i)
1594                for i, school in enumerate(school_list)
1595            }
1596
1597            # 收集结果
1598            for future in as_completed(future_to_school):
1599                school, thread_id = future_to_school[future]
1600                try:
1601                    school_data = future.result()
1602                    if school_data:
1603                        all_data.extend(school_data)
1604                        logging.info(f"线程 {thread_id} 完成学校 {school['name']} 的爬取")
1605                except Exception as e:
1606                    logging.error(f"学校 {school['name']} 爬取失败: {e}")
1607
1608        logging.info(f"多线程爬取完成，共获取 {len(all_data)} 条专业信息")
1609        return all_data
1610
1611    def get_available_regions(self):
1612        """获取所有可用地区"""
1613        temp_spider = ThreadSafeSpider(self.db_config, 0)
1614        try:
1615            temp_spider.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
1616            time.sleep(5)  # 增加等待时间
1617
1618            print("\n=== 可用地区 ===")
1619            area_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".area-item")
1620            all_regions = []
1621
1622            for area_item in area_items:
1623                regions = area_item.find_elements(By.CSS_SELECTOR, ".option-item")
1624                for region in regions:
1625                    region_name = region.text.strip()
1626                    all_regions.append(region_name)
1627
1628            # 横向显示地区
1629            print("\n一区:", end=" ")
1630            for i, region in enumerate(all_regions[:21]):
1631                print(f"{i + 1}.{region}", end=" ")
1632
1633            print("\n\n二区:", end=" ")
1634            for i, region in enumerate(all_regions[21:], 22):
1635                print(f"{i}.{region}", end=" ")
1636            print()
1637
1638            return all_regions
1639
1640        except Exception as e:
1641            logging.error(f"获取可用地区失败: {e}")
1642            return []
1643        finally:
1644            temp_spider.close()
1645
1646    def select_search_mode(self):
1647        """选择搜索模式"""
1648        print("\n=== 搜索模式选择 ===")
1649        print("1. 按地区搜索")
1650        print("2. 按学校搜索")
1651
1652        while True:
1653            mode = input("请选择搜索模式 (1 或 2): ").strip()
1654            if mode == "1":
1655                return "region"
1656            elif mode == "2":
1657                return "school"
1658            else:
1659                print("无效选择，请重新输入")
1660
1661    def select_region_and_features(self):
1662        """交互式选择地区和院校特性"""
1663        try:
1664            all_regions = self.get_available_regions()
1665            if not all_regions:
1666                return [], []
1667
1668            print("\n=== 地区选择 ===")
1669            print("请选择要爬取的地区（输入编号，多个编号用逗号分隔，输入0选择所有地区）:")
1670
1671            region_input = input("请输入编号: ").strip()
1672
1673            selected_regions = []
1674            if region_input == "0":
1675                selected_regions = all_regions
1676            else:
1677                input_nums = [num.strip() for num in region_input.split(',') if num.strip()]
1678                for num in input_nums:
1679                    if num.isdigit() and 1 <= int(num) <= len(all_regions):
1680                        selected_regions.append(all_regions[int(num) - 1])
1681                    else:
1682                        print(f"警告: 无效编号 {num}，已跳过")
1683
1684            if not selected_regions:
1685                print("未选择任何有效地区")
1686                return [], []
1687
1688            # 院校特性选择
1689            print("\n=== 院校特性 ===")
1690            feature_options = [
1691                ("bs", "博士点"),
1692                ("syl", "双一流建设高校"),
1693                ("zhx", "自划线院校")
1694            ]
1695
1696            print("请选择院校特性（输入编号，多个编号用逗号分隔，输入0选择所有特性，直接回车跳过选择）:")
1697            for idx, (value, name) in enumerate(feature_options, 1):
1698                print(f"  {idx}. {name}")
1699
1700            feature_input = input("请输入编号: ").strip()
1701
1702            selected_features = []
1703            if feature_input == "":
1704                print("未选择任何院校特性，将搜索所有院校")
1705            elif feature_input == "0":
1706                selected_features = [value for value, name in feature_options]
1707            else:
1708                input_nums = [num.strip() for num in feature_input.split(',') if num.strip()]
1709                for num in input_nums:
1710                    if num.isdigit() and 1 <= int(num) <= len(feature_options):
1711                        selected_features.append(feature_options[int(num) - 1][0])
1712                    else:
1713                        print(f"警告: 无效编号 {num}，已跳过")
1714
1715            return selected_regions, selected_features
1716
1717        except Exception as e:
1718            logging.error(f"选择地区和特性失败: {e}")
1719            return [], []
1720
1721    def select_schools_by_name(self):
1722        """按学校名称选择学校"""
1723        print("\n=== 学校搜索 ===")
1724        print("请输入要爬取的学校名称（多个学校用逗号分隔）:")
1725
1726        school_input = input("请输入学校名称: ").strip()
1727
1728        if not school_input:
1729            print("未输入任何学校名称")
1730            return []
1731
1732        school_names = [name.strip() for name in school_input.split(',') if name.strip()]
1733        return school_names
1734
1735    def search_schools_by_region_and_features(self, region, features):
1736        """根据地区和特性搜索学校"""
1737        temp_spider = ThreadSafeSpider(self.db_config, 0)
1738        try:
1739            temp_spider.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
1740            time.sleep(3)  # 增加等待时间
1741
1742            # 选择地区
1743            area_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".area-item")
1744            region_found = False
1745            for area_item in area_items:
1746                regions = area_item.find_elements(By.CSS_SELECTOR, ".option-item")
1747                for region_elem in regions:
1748                    if region_elem.text.strip() == region:
1749                        region_elem.click()
1750                        region_found = True
1751                        break
1752                if region_found:
1753                    break
1754
1755            if not region_found:
1756                logging.error(f"无法选择地区: {region}")
1757                return []
1758
1759            # 选择特性
1760            if features:
1761                for feature in features:
1762                    try:
1763                        checkbox = temp_spider.driver.find_element(By.CSS_SELECTOR,
1764                                                                   f"input[type='checkbox'][value='{feature}']")
1765                        if not checkbox.is_selected():
1766                            checkbox.click()
1767                    except:
1768                        pass
1769
1770            # 搜索
1771            search_button = temp_spider.wait_for_element_clickable(By.CSS_SELECTOR, "button.ivu-btn-primary")
1772            if search_button:
1773                search_button.click()
1774                time.sleep(3)  # 增加等待时间
1775
1776            schools = []
1777            school_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".zy-item")
1778            for item in school_items:
1779                try:
1780                    name_elem = item.find_element(By.CSS_SELECTOR, ".yx-name")
1781                    school_name = name_elem.text.strip()
1782                    clean_name = re.sub(r'\(\d+\)', '', school_name).strip()
1783
1784                    school_features = []
1785                    try:
1786                        feature_tags = item.find_elements(By.CSS_SELECTOR, ".yx-tag")
1787                        for tag in feature_tags:
1788                            feature_text = tag.text.strip()
1789                            if feature_text:
1790                                school_features.append(feature_text)
1791                    except:
1792                        pass
1793
1794                    major_link_elem = item.find_element(By.CSS_SELECTOR, ".zy-btn")
1795                    major_link = major_link_elem.get_attribute("href")
1796
1797                    schools.append({
1798                        'name': clean_name,
1799                        'original_name': school_name,
1800                        'major_link': major_link,
1801                        'features': school_features
1802                    })
1803                except:
1804                    continue
1805
1806            logging.info(f"地区 {region} 找到 {len(schools)} 所学校")
1807            return schools
1808
1809        except Exception as e:
1810            logging.error(f"搜索学校失败 - 地区: {region}, 特性: {features}: {e}")
1811            return []
1812        finally:
1813            temp_spider.close()
1814
1815    def search_school_by_name(self, school_name):
1816        """根据学校名称搜索学校"""
1817        temp_spider = ThreadSafeSpider(self.db_config, 0)
1818        try:
1819            temp_spider.driver.get("https://yz.chsi.com.cn/zsml/dw.do")
1820            time.sleep(3)  # 增加等待时间
1821
1822            school_search_input = temp_spider.wait_for_element(
1823                By.CSS_SELECTOR, "input[placeholder='请输入招生单位名称']"
1824            )
1825            if not school_search_input:
1826                logging.error("未找到学校搜索框")
1827                return None
1828
1829            school_search_input.clear()
1830            school_search_input.send_keys(school_name)
1831            time.sleep(3)
1832
1833            search_button = temp_spider.wait_for_element_clickable(
1834                By.CSS_SELECTOR, "button.ivu-btn-primary"
1835            )
1836            if search_button:
1837                search_button.click()
1838                time.sleep(3)  # 增加等待时间
1839            else:
1840                logging.error("未找到查询按钮")
1841                return None
1842
1843            if temp_spider.check_no_results():
1844                logging.warning(f"未找到学校: {school_name}")
1845                return None
1846
1847            # 获取学校信息
1848            school_items = temp_spider.driver.find_elements(By.CSS_SELECTOR, ".zy-item")
1849            if school_items:
1850                item = school_items[0]
1851                name_elem = item.find_element(By.CSS_SELECTOR, ".yx-name")
1852                school_name = name_elem.text.strip()
1853                clean_name = re.sub(r'\(\d+\)', '', school_name).strip()
1854
1855                school_features = []
1856                try:
1857                    feature_tags = item.find_elements(By.CSS_SELECTOR, ".yx-tag")
1858                    for tag in feature_tags:
1859                        feature_text = tag.text.strip()
1860                        if feature_text:
1861                            school_features.append(feature_text)
1862                except:
1863                    pass
1864
1865                major_link_elem = item.find_element(By.CSS_SELECTOR, ".zy-btn")
1866                major_link = major_link_elem.get_attribute("href")
1867
1868                return {
1869                    'name': clean_name,
1870                    'original_name': school_name,
1871                    'major_link': major_link,
1872                    'features': school_features
1873                }
1874            else:
1875                logging.warning(f"未找到学校: {school_name}")
1876                return None
1877
1878        except Exception as e:
1879            logging.error(f"搜索学校 {school_name} 失败: {e}")
1880            return None
1881        finally:
1882            temp_spider.close()
1883
1884    def crawl_by_regions_and_features(self, regions, features):
1885        """按地区和特性爬取所有学校（多线程版本）"""
1886        all_data = []
1887        total_schools = 0
1888
1889        for region in regions:
1890            logging.info(f"=== 开始处理地区: {region} ===")
1891
1892            schools = self.search_schools_by_region_and_features(region, features)
1893
1894            if not schools:
1895                logging.info(f"地区 {region} 没有找到符合条件的学校")
1896                continue
1897
1898            # 询问用户对已存在学校的处理方式
1899            filtered_schools = self.ask_user_for_existing_schools(schools, 'region')
1900
1901            if not filtered_schools:
1902                logging.info(f"地区 {region} 没有需要爬取的学校")
1903                continue
1904
1905            logging.info(f"地区 {region} 找到 {len(filtered_schools)} 所学校需要爬取，开始多线程爬取专业信息...")
1906
1907            region_data = self.crawl_all_schools_multithread(filtered_schools, region, 'region')
1908            all_data.extend(region_data)
1909            total_schools += len(filtered_schools)
1910
1911            logging.info(f"地区 {region} 爬取完成，共获取 {len(region_data)} 条专业信息")
1912
1913        logging.info(f"所有地区爬取完成，共处理 {total_schools} 所学校，获取 {len(all_data)} 条专业信息")
1914        return all_data
1915
1916    def crawl_by_school_names(self, school_names):
1917        """按学校名称爬取学校专业信息（多线程版本）"""
1918        all_data = []
1919
1920        # 准备学校信息列表
1921        schools_to_crawl = []
1922        for school_name in school_names:
1923            logging.info(f"搜索学校: {school_name}")
1924            school_info = self.search_school_by_name(school_name)
1925            if school_info:
1926                schools_to_crawl.append(school_info)
1927            else:
1928                logging.warning(f"未找到学校: {school_name}")
1929
1930        if not schools_to_crawl:
1931            logging.error("没有找到任何有效的学校")
1932            return all_data
1933
1934        # 询问用户对已存在学校的处理方式
1935        filtered_schools = self.ask_user_for_existing_schools(schools_to_crawl, 'school')
1936
1937        if not filtered_schools:
1938            logging.info("没有需要爬取的学校")
1939            return all_data
1940
1941        logging.info(f"找到 {len(filtered_schools)} 所有效学校需要爬取，开始多线程爬取...")
1942
1943        # 使用多线程版本
1944        all_data = self.crawl_all_schools_multithread(filtered_schools, None, 'school')
1945
1946        logging.info(f"所有学校爬取完成，共处理 {len(filtered_schools)} 所学校，获取 {len(all_data)} 条专业信息")
1947        return all_data
1948
1949    def close(self):
1950        """清理资源"""
1951        pass
1952
1953
1954class ShanghaiRankingSpider:
1955    """软科排名爬虫类 - 使用指定路径的Edge驱动"""
1956
1957    def __init__(self, headless=False):
1958        # 数据库配置
1959        self.db_config = {
1960            'host': 'localhost',
1961            'user': 'root',
1962            'password': 'Wza!64416685',
1963            'database': 'kaoyan_data'
1964        }
1965
1966        # 浏览器配置
1967        self.headless = headless
1968        self.driver = None
1969        self.wait = None
1970
1971        # 指定Edge驱动路径
1972        self.edge_driver_path = r"D:\work and study\person\数据库\爬虫+数据库\msedgedriver.exe"
1973
1974        self.setup_driver()
1975
1976        # 学科定义
1977        self.subjects_2025 = {
1978            # 理学 (07)
1979            '07': [
1980                ('0701', '数学'),
1981                ('0702', '物理学'),
1982                ('0703', '化学'),
1983                ('0704', '天文学'),
1984                ('0705', '地理学'),
1985                ('0706', '大气科学'),
1986                ('0707', '海洋科学'),
1987                ('0708', '地球物理学'),
1988                ('0709', '地质学'),
1989                ('0710', '生物学'),
1990                ('0711', '系统科学'),
1991                ('0712', '科学技术史'),
1992                ('0713', '生态学'),
1993                ('0714', '统计学'),
1994            ],
1995            # 工学 (08)
1996            '08': [
1997                ('0801', '力学'),
1998                ('0802', '机械工程'),
1999                ('0803', '光学工程'),
2000                ('0804', '仪器科学与技术'),
2001                ('0805', '材料科学与工程'),
2002                ('0806', '冶金工程'),
2003                ('0807', '动力工程及工程热物理'),
2004                ('0808', '电气工程'),
2005                ('0809', '电子科学与技术'),
2006                ('0810', '信息与通信工程'),
2007                ('0811', '控制科学与工程'),
2008                ('0812', '计算机科学与技术'),
2009                ('0813', '建筑学'),
2010                ('0814', '土木工程'),
2011                ('0815', '水利工程'),
2012                ('0816', '测绘科学与技术'),
2013                ('0817', '化学工程与技术'),
2014                ('0818', '地质资源与地质工程'),
2015                ('0819', '矿业工程'),
2016                ('0820', '石油与天然气工程'),
2017                ('0821', '纺织科学与工程'),
2018                ('0822', '轻工技术与工程'),
2019                ('0823', '交通运输工程'),
2020                ('0824', '船舶与海洋工程'),
2021                ('0825', '航空宇航科学与技术'),
2022                ('0826', '兵器科学与技术'),
2023                ('0827', '核科学与技术'),
2024                ('0828', '农业工程'),
2025                ('0829', '林业工程'),
2026                ('0830', '环境科学与工程'),
2027                ('0831', '生物医学工程'),
2028                ('0832', '食品科学与工程'),
2029                ('0833', '城乡规划学'),
2030                ('0835', '软件工程'),
2031                ('0836', '生物工程'),
2032                ('0837', '安全科学与工程'),
2033                ('0839', '网络空间安全'),
2034            ]
2035        }
2036
2037        # 创建数据库表
2038        self.create_tables()
2039
2040    def setup_driver(self):
2041        """配置Edge浏览器驱动 - 使用指定路径的驱动"""
2042        try:
2043            edge_options = EdgeOptions()
2044
2045            # 如果用户指定了无头模式
2046            if self.headless:
2047                edge_options.add_argument('--headless')
2048                edge_options.add_argument('--disable-gpu')
2049
2050            edge_options.add_argument('--no-sandbox')
2051            edge_options.add_argument('--disable-dev-shm-usage')
2052            edge_options.add_argument('--window-size=1920,1080')
2053            edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
2054            edge_options.add_experimental_option('useAutomationExtension', False)
2055            edge_options.add_argument('--disable-blink-features=AutomationControlled')
2056
2057            # 模拟真实浏览器
2058            edge_options.add_argument(
2059                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
2060            )
2061
2062            # 检查驱动文件是否存在
2063            if not os.path.exists(self.edge_driver_path):
2064                logging.error(f"Edge驱动文件不存在: {self.edge_driver_path}")
2065                print(f"\n错误: Edge驱动文件不存在: {self.edge_driver_path}")
2066                print("请确保驱动文件已下载并放置在正确位置")
2067                print("驱动下载地址: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
2068                raise FileNotFoundError(f"Edge驱动文件不存在: {self.edge_driver_path}")
2069
2070            logging.info(f"使用Edge驱动路径: {self.edge_driver_path}")
2071
2072            # 创建Edge服务并指定驱动路径
2073            service = EdgeService(executable_path=self.edge_driver_path)
2074
2075            # 创建driver
2076            self.driver = webdriver.Edge(service=service, options=edge_options)
2077
2078            # 防止被检测为自动化工具
2079            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
2080
2081            # 设置WebDriverWait
2082            self.wait = WebDriverWait(self.driver, 10)
2083
2084            # 设置隐式等待
2085            self.driver.implicitly_wait(5)
2086
2087            logging.info("浏览器驱动初始化成功")
2088
2089        except Exception as e:
2090            logging.error(f"浏览器驱动初始化失败: {e}")
2091            print(f"\n浏览器驱动初始化失败: {e}")
2092            print("\n可能的解决方案:")
2093            print(f"1. 检查驱动文件是否存在: {self.edge_driver_path}")
2094            print("2. 确保Edge浏览器已安装并更新到最新版本")
2095            print("3. 尝试重新下载Edge驱动:")
2096            print("   - 下载地址: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
2097            print("   - 选择与你的Edge浏览器版本匹配的驱动")
2098            print("   - 下载后解压，将msedgedriver.exe放到上述路径")
2099            raise
2100
2101    def wait_for_element(self, by, value, timeout=10):
2102        """等待元素出现"""
2103        try:
2104            element = WebDriverWait(self.driver, timeout).until(
2105                EC.presence_of_element_located((by, value))
2106            )
2107            return element
2108        except TimeoutException:
2109            logging.warning(f"等待元素超时: {by}={value}")
2110            return None
2111
2112    def wait_for_element_clickable(self, by, value, timeout=10):
2113        """等待元素可点击"""
2114        try:
2115            element = WebDriverWait(self.driver, timeout).until(
2116                EC.element_to_be_clickable((by, value))
2117            )
2118            return element
2119        except TimeoutException:
2120            logging.warning(f"等待元素可点击超时: {by}={value}")
2121            return None
2122
2123    def wait_for_page_load(self, timeout=30):
2124        """等待页面加载完成"""
2125        try:
2126            WebDriverWait(self.driver, timeout).until(
2127                lambda driver: driver.execute_script("return document.readyState") == "complete"
2128            )
2129            return True
2130        except TimeoutException:
2131            logging.warning("页面加载超时")
2132            return False
2133
2134    def get_db_connection(self):
2135        """获取数据库连接"""
2136        try:
2137            connection = mysql.connector.connect(**self.db_config)
2138            return connection
2139        except Error as e:
2140            logging.error(f"数据库连接失败: {e}")
2141            return None
2142
2143    def create_tables(self):
2144        """创建软科排名数据表"""
2145        connection = self.get_db_connection()
2146        if not connection:
2147            return False
2148
2149        try:
2150            cursor = connection.cursor()
2151
2152            # 先检查表是否存在，如果存在且结构不对则删除重建
2153            cursor.execute("SHOW TABLES LIKE 'shanghai_subject_rankings'")
2154            table_exists = cursor.fetchone()
2155
2156            if table_exists:
2157                # 检查表结构是否包含ranking_position_2025列
2158                try:
2159                    cursor.execute("SELECT ranking_position_2025 FROM shanghai_subject_rankings LIMIT 1")
2160                    logging.info("表结构正确，无需重建")
2161                except mysql.connector.Error:
2162                    # 表存在但结构不对，删除重建
2163                    logging.info("表结构不正确，删除重建...")
2164                    cursor.execute("DROP TABLE IF EXISTS shanghai_subject_rankings")
2165                    connection.commit()
2166
2167            # 创建学科排名表（如果不存在）
2168            cursor.execute("""
2169                CREATE TABLE IF NOT EXISTS shanghai_subject_rankings (
2170                    id INT AUTO_INCREMENT PRIMARY KEY,
2171                    year INT NOT NULL,
2172                    subject_code VARCHAR(20) NOT NULL,
2173                    subject_name VARCHAR(100) NOT NULL,
2174                    ranking_position_2025 INT,
2175                    ranking_position_2024 INT,
2176                    school_name VARCHAR(255) NOT NULL,
2177                    score_2025 FLOAT,
2178                    score_2024 FLOAT,
2179                    indicator_scores_2025 JSON,
2180                    indicator_scores_2024 JSON,
2181                    subject_category VARCHAR(50),
2182                    page_number INT DEFAULT 1,
2183                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
2184                    UNIQUE KEY unique_year_subject_school (year, subject_code, school_name),
2185                    INDEX idx_year_subject (year, subject_code),
2186                    INDEX idx_school_name (school_name),
2187                    INDEX idx_subject_category (subject_category),
2188                    INDEX idx_page_number (page_number)
2189                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
2190            """)
2191
2192            connection.commit()
2193            logging.info("软科排名数据表创建/更新成功")
2194            return True
2195
2196        except Error as e:
2197            logging.error(f"创建/更新软科排名表失败: {e}")
2198            return False
2199        finally:
2200            if connection.is_connected():
2201                cursor.close()
2202                connection.close()
2203
2204    def clean_school_name(self, school_name):
2205        """清理学校名称"""
2206        if not school_name:
2207            return ""
2208
2209        # 移除空格和特殊字符
2210        school_name = school_name.strip()
2211
2212        # 移除括号内的内容（如校区信息）
2213        school_name = re.sub(r'\([^)]*\)', '', school_name)
2214        school_name = re.sub(r'（[^）]*）', '', school_name)
2215
2216        # 移除多余空格
2217        school_name = re.sub(r'\s+', ' ', school_name).strip()
2218
2219        # 处理特殊情况
2220        replacements = {
2221            '北京协和医学院(清华大学医学部)': '北京协和医学院',
2222            '国防科技大学（原国防科学技术大学）': '国防科技大学',
2223            '北京航空航天大学（原北京航空航天大学）': '北京航空航天大学',
2224            '北京理工大学（原北京航空航天大学）': '北京理工大学',
2225            '哈尔滨工业大学（原哈尔滨工业大学）': '哈尔滨工业大学',
2226            '西北工业大学（原西北工业大学）': '西北工业大学',
2227            '北京大学医学部': '北京大学',
2228            '复旦大学上海医学院': '复旦大学',
2229            '上海交通大学医学院': '上海交通大学',
2230        }
2231
2232        for old, new in replacements.items():
2233            if old in school_name:
2234                school_name = school_name.replace(old, new)
2235
2236        return school_name
2237
2238    def extract_rank_number(self, rank_text):
2239        """从排名文本中提取排名数字"""
2240        if not rank_text:
2241            return 0
2242
2243        rank_text = str(rank_text).strip()
2244
2245        # 如果是数字直接返回
2246        if rank_text.isdigit():
2247            return int(rank_text)
2248        elif '-' in rank_text:
2249            # 处理 "1-2" 这样的排名范围，取第一个数字
2250            parts = rank_text.split('-')
2251            if parts[0].strip().isdigit():
2252                return int(parts[0].strip())
2253            else:
2254                # 尝试提取数字
2255                match = re.search(r'(\d+)', parts[0].strip())
2256                if match:
2257                    return int(match.group(1))
2258        else:
2259            # 尝试提取数字
2260            match = re.search(r'(\d+)', rank_text)
2261            if match:
2262                return int(match.group(1))
2263
2264        return 0
2265
2266    def extract_score(self, score_text):
2267        """从分数文本中提取分数"""
2268        if not score_text:
2269            return 0.0
2270
2271        try:
2272            # 移除非数字字符（除了小数点）
2273            cleaned_text = re.sub(r'[^\d.]', '', str(score_text))
2274            if cleaned_text:
2275                return float(cleaned_text)
2276            return 0.0
2277        except:
2278            return 0.0
2279
2280    def navigate_to_subject_page(self, subject_code):
2281        """导航到学科页面"""
2282        url = f"https://www.shanghairanking.cn/rankings/bcsr/2025/{subject_code}"
2283        logging.info(f"导航到: {url}")
2284
2285        try:
2286            self.driver.get(url)
2287
2288            # 等待页面加载完成
2289            if not self.wait_for_page_load():
2290                logging.warning("页面加载可能未完成，继续尝试...")
2291
2292            # 等待表格出现
2293            table = self.wait_for_element(By.CLASS_NAME, "rk-table", timeout=20)
2294            if not table:
2295                logging.error("未找到排名表格")
2296                return False
2297
2298            # 等待表格数据加载
2299            time.sleep(3)
2300            logging.info("页面加载完成")
2301            return True
2302
2303        except TimeoutException:
2304            logging.error("页面加载超时")
2305            try:
2306                self.driver.save_screenshot(f"timeout_{subject_code}.png")
2307                logging.info(f"已保存截图: timeout_{subject_code}.png")
2308            except:
2309                pass
2310            return False
2311        except Exception as e:
2312            logging.error(f"导航到页面失败: {e}")
2313            return False
2314
2315    def get_total_pages(self):
2316        """获取总页数"""
2317        try:
2318            # 等待分页器加载
2319            pagination = self.wait_for_element(By.CLASS_NAME, "ant-pagination", timeout=15)
2320            if not pagination:
2321                logging.warning("未找到分页器")
2322                return 1
2323
2324            # 等待分页器完全渲染
2325            time.sleep(2)
2326
2327            # 方法1: 查找总页数文本
2328            try:
2329                total_text_element = pagination.find_element(By.CLASS_NAME, "ant-pagination-total-text")
2330                text = total_text_element.text
2331                match = re.search(r'共\s*(\d+)\s*条', text)
2332                if match:
2333                    total_items = int(match.group(1))
2334                    total_pages = (total_items + 29) // 30  # 每页30条
2335                    logging.info(f"总条目: {total_items}, 总页数: {total_pages}")
2336                    return total_pages
2337            except NoSuchElementException:
2338                pass
2339
2340            # 方法2: 查找所有页码按钮，取最大值
2341            try:
2342                page_buttons = pagination.find_elements(By.CLASS_NAME, "ant-pagination-item")
2343                if page_buttons:
2344                    page_numbers = []
2345                    for button in page_buttons:
2346                        try:
2347                            button_text = button.text.strip()
2348                            if button_text and button_text.isdigit():
2349                                page_num = int(button_text)
2350                                page_numbers.append(page_num)
2351                        except:
2352                            continue
2353
2354                    if page_numbers:
2355                        max_page = max(page_numbers)
2356                        logging.info(f"从页码按钮获取总页数: {max_page}")
2357                        return max_page
2358            except Exception as e:
2359                logging.debug(f"方法2失败: {e}")
2360
2361            # 默认返回1页
2362            logging.info("无法获取总页数，默认返回1页")
2363            return 1
2364
2365        except Exception as e:
2366            logging.warning(f"获取总页数失败: {e}")
2367            return 1
2368
2369    def go_to_page(self, page_num):
2370        """跳转到指定页码 - 改进版"""
2371        try:
2372            logging.info(f"尝试跳转到第 {page_num} 页")
2373
2374            # 等待分页器加载
2375            pagination = self.wait_for_element(By.CLASS_NAME, "ant-pagination", timeout=15)
2376            if not pagination:
2377                logging.error("未找到分页器")
2378                return False
2379
2380            # 方法1: 直接点击页码按钮（最可靠）
2381            try:
2382                # 查找所有页码按钮
2383                page_buttons = pagination.find_elements(By.CLASS_NAME, "ant-pagination-item")
2384                logging.info(f"找到 {len(page_buttons)} 个页码按钮")
2385
2386                target_button = None
2387                for button in page_buttons:
2388                    try:
2389                        button_text = button.text.strip()
2390                        if button_text and button_text.isdigit() and int(button_text) == page_num:
2391                            target_button = button
2392                            break
2393                    except:
2394                        continue
2395
2396                if target_button:
2397                    # 检查是否已经是当前页
2398                    class_attr = target_button.get_attribute("class")
2399                    if "ant-pagination-item-active" in class_attr:
2400                        logging.info(f"已经是第 {page_num} 页")
2401                        return True
2402
2403                    # 滚动到元素位置
2404                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
2405                                               target_button)
2406                    time.sleep(1)
2407
2408                    # 使用JavaScript点击，避免元素不可点击的问题
2409                    self.driver.execute_script("arguments[0].click();", target_button)
2410                    logging.info(f"通过JavaScript点击跳转到第 {page_num} 页")
2411
2412                    # 等待页面加载
2413                    self.wait_for_page_load()
2414                    time.sleep(3)
2415
2416                    # 验证是否跳转成功
2417                    active_page = self.wait_for_element(By.CSS_SELECTOR, ".ant-pagination-item-active", timeout=10)
2418                    if active_page:
2419                        active_page_num = active_page.text.strip()
2420                        if active_page_num.isdigit() and int(active_page_num) == page_num:
2421                            logging.info(f"成功跳转到第 {page_num} 页")
2422                            return True
2423                    else:
2424                        # 重新检查当前页码
2425                        time.sleep(2)
2426                        # 再次查找当前激活的页码
2427                        try:
2428                            active_page = self.driver.find_element(By.CSS_SELECTOR, ".ant-pagination-item-active")
2429                            active_page_num = active_page.text.strip()
2430                            if active_page_num.isdigit() and int(active_page_num) == page_num:
2431                                logging.info(f"成功跳转到第 {page_num} 页（二次验证）")
2432                                return True
2433                        except:
2434                            pass
2435            except Exception as e:
2436                logging.debug(f"方法1失败: {e}")
2437
2438            # 方法2: 使用页码输入框（快速跳转）
2439            try:
2440                quick_jumper = pagination.find_element(By.CLASS_NAME, "ant-pagination-options-quick-jumper")
2441                page_input = quick_jumper.find_element(By.TAG_NAME, "input")
2442
2443                # 滚动到输入框
2444                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
2445                                           page_input)
2446                time.sleep(1)
2447
2448                # 清空并输入页码
2449                page_input.clear()
2450                page_input.send_keys(str(page_num))
2451                page_input.send_keys(Keys.RETURN)
2452
2453                logging.info(f"使用输入框跳转到第 {page_num} 页")
2454
2455                # 等页面加载
2456                self.wait_for_page_load()
2457                time.sleep(4)
2458
2459                # 验证跳转
2460                active_page = self.wait_for_element(By.CSS_SELECTOR, ".ant-pagination-item-active", timeout=10)
2461                if active_page:
2462                    active_page_num = active_page.text.strip()
2463                    if active_page_num.isdigit() and int(active_page_num) == page_num:
2464                        logging.info(f"输入框跳转成功到第 {page_num} 页")
2465                        return True
2466            except Exception as e:
2467                logging.debug(f"方法2失败: {e}")
2468
2469            # 方法3: 模拟点击下一页按钮多次
2470            try:
2471                current_page = 1
2472
2473                # 获取当前页码
2474                try:
2475                    active_page = pagination.find_element(By.CLASS_NAME, "ant-pagination-item-active")
2476                    current_page_text = active_page.text.strip()
2477                    if current_page_text.isdigit():
2478                        current_page = int(current_page_text)
2479                except:
2480                    pass
2481
2482                # 如果目标页大于当前页，点击"下一页"
2483                if page_num > current_page:
2484                    clicks_needed = page_num - current_page
2485                    for click_count in range(clicks_needed):
2486                        next_button = pagination.find_element(By.CLASS_NAME, "ant-pagination-next")
2487
2488                        # 检查是否已禁用
2489                        if "ant-pagination-disabled" in next_button.get_attribute("class"):
2490                            logging.warning(f"下一页按钮已禁用，可能已到最后一页")
2491                            break
2492
2493                        # 滚动并点击
2494                        self.driver.execute_script(
2495                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", next_button)
2496                        time.sleep(1)
2497
2498                        # 使用JavaScript点击
2499                        self.driver.execute_script("arguments[0].click();", next_button)
2500
2501                        logging.info(f"点击下一页 ({current_page + click_count} -> {current_page + click_count + 1})")
2502
2503                        # 等待页面加载
2504                        self.wait_for_page_load()
2505                        time.sleep(3)
2506
2507                        # 重新获取分页器
2508                        pagination = self.wait_for_element(By.CLASS_NAME, "ant-pagination", timeout=10)
2509                        if not pagination:
2510                            logging.warning("分页器丢失")
2511                            break
2512
2513                    # 验证最终页码
2514                    time.sleep(2)
2515                    final_active_page = self.wait_for_element(By.CSS_SELECTOR, ".ant-pagination-item-active",
2516                                                              timeout=10)
2517                    if final_active_page:
2518                        final_page_text = final_active_page.text.strip()
2519                        if final_page_text.isdigit() and int(final_page_text) == page_num:
2520                            logging.info(f"通过下一页按钮成功跳转到第 {page_num} 页")
2521                            return True
2522                else:
2523                    logging.warning(f"目标页 {page_num} 不大于当前页 {current_page}")
2524            except Exception as e:
2525                logging.debug(f"方法3失败: {e}")
2526
2527            logging.warning(f"无法跳转到第 {page_num} 页")
2528            return False
2529
2530        except Exception as e:
2531            logging.error(f"跳转到第 {page_num} 页失败: {e}")
2532            return False
2533
2534    def parse_current_page(self, subject_code, subject_name, page_num=1):
2535        """解析当前页面的数据 - 同时获取2025和2024排名"""
2536        try:
2537            # 等待表格加载
2538            table = self.wait_for_element(By.CLASS_NAME, "rk-table", timeout=15)
2539            if not table:
2540                logging.warning("未找到排名表格")
2541                return []
2542
2543            # 获取页面HTML
2544            page_source = self.driver.page_source
2545            soup = BeautifulSoup(page_source, 'html.parser')
2546
2547            # 查找排名表格
2548            table = soup.find('table', class_='rk-table')
2549            if not table:
2550                logging.warning("未找到排名表格")
2551                return []
2552
2553            # 解析表头
2554            headers = []
2555            thead = table.find('thead')
2556            if thead:
2557                header_cells = thead.find_all('th')
2558                headers = [cell.get_text(strip=True) for cell in header_cells]
2559
2560            logging.info(f"表头信息: {headers}")
2561
2562            # 根据表头确定列索引 - 简化逻辑
2563            # 从HTML结构看，列顺序是固定的：
2564            # 第0列: 2025排名
2565            # 第1列: 2024排名（可能带灰色样式）
2566            # 第2列: 层次信息
2567            # 第3列: 学校名称
2568            # 第4列: 总分
2569            col_indices = {
2570                'rank_2025': 0,  # 固定第0列是2025排名
2571                'rank_2024': 1,  # 固定第1列是2024排名
2572                'school': 3,  # 固定第3列是学校名称
2573                'score_2025': 4  # 固定第4列是总分
2574            }
2575
2576            logging.info(f"使用固定列索引: {col_indices}")
2577
2578            # 提取数据行
2579            tbody = table.find('tbody')
2580            if not tbody:
2581                return []
2582
2583            rows = tbody.find_all('tr')
2584            data_rows = []
2585
2586            for row in rows:
2587                cells = row.find_all('td')
2588                # 检查是否有足够的列
2589                if len(cells) < 5:  # 至少需要5列
2590                    continue
2591
2592                try:
2593                    # 解析2025排名 - 第0列
2594                    rank_2025 = 0
2595                    if len(cells) > col_indices['rank_2025']:
2596                        # 直接获取排名数字，可能包含在div中
2597                        rank_cell = cells[col_indices['rank_2025']]
2598                        # 查找div.ranking或者直接获取文本
2599                        rank_div = rank_cell.find('div', class_='ranking')
2600                        if rank_div:
2601                            rank_text = rank_div.get_text(strip=True)
2602                        else:
2603                            rank_text = rank_cell.get_text(strip=True)
2604                        rank_2025 = self.extract_rank_number(rank_text)
2605
2606                    # 解析2024排名 - 第1列
2607                    rank_2024 = 0
2608                    if len(cells) > col_indices['rank_2024']:
2609                        rank_cell = cells[col_indices['rank_2024']]
2610                        # 2024排名可能包含在span中或有特殊样式
2611                        rank_span = rank_cell.find('span')
2612                        if rank_span:
2613                            rank_text = rank_span.get_text(strip=True)
2614                        else:
2615                            rank_text = rank_cell.get_text(strip=True)
2616                        rank_2024 = self.extract_rank_number(rank_text)
2617
2618                    # 解析学校名称 - 第3列
2619                    school_name = ""
2620                    if len(cells) > col_indices['school']:
2621                        school_cell = cells[col_indices['school']]
2622                        # 学校名称可能在span.name-cn中
2623                        name_span = school_cell.find('span', class_='name-cn')
2624                        if name_span:
2625                            school_name = self.clean_school_name(name_span.get_text(strip=True))
2626                        else:
2627                            school_name = self.clean_school_name(school_cell.get_text(strip=True))
2628
2629                    if not school_name or len(school_name) < 2:
2630                        continue
2631
2632                    # 解析2025分数 - 第4列
2633                    score_2025 = 0.0
2634                    if len(cells) > col_indices['score_2025']:
2635                        score_text = cells[col_indices['score_2025']].get_text(strip=True)
2636                        score_2025 = self.extract_score(score_text)
2637
2638                    # 2024分数通常不单独显示，设为0.0
2639                    score_2024 = 0.0
2640
2641                    # 确定学科类别
2642                    subject_category = "理学" if subject_code.startswith('07') else "工学"
2643
2644                    data_rows.append({
2645                        'year': 2025,  # 主年份为2025
2646                        'subject_code': subject_code,
2647                        'subject_name': subject_name,
2648                        'ranking_position_2025': rank_2025,
2649                        'ranking_position_2024': rank_2024,
2650                        'school_name': school_name,
2651                        'score_2025': score_2025,
2652                        'score_2024': score_2024,
2653                        'indicator_scores_2025': '{}',
2654                        'indicator_scores_2024': '{}',
2655                        'subject_category': subject_category,
2656                        'page_number': page_num
2657                    })
2658
2659                except Exception as e:
2660                    logging.debug(f"解析行数据失败: {e}")
2661                    continue
2662
2663            logging.info(f"成功解析 {len(data_rows)} 条数据")
2664
2665            # 显示样本数据
2666            if data_rows and page_num <= 2:
2667                logging.info(f"第{page_num}页样本数据:")
2668                for i, data in enumerate(data_rows[:3]):
2669                    logging.info(f"  排名2025:{data['ranking_position_2025']}, "
2670                                 f"排名2024:{data['ranking_position_2024']}, "
2671                                 f"{data['school_name']} "
2672                                 f"分数:{data['score_2025']:.1f}")
2673
2674            return data_rows
2675
2676        except Exception as e:
2677            logging.error(f"解析页面数据失败: {e}")
2678            return []
2679
2680    def fetch_subject_data(self, subject_code, subject_name, max_pages=None):
2681        """获取学科所有页面数据"""
2682        logging.info(f"开始爬取学科排名: {subject_name} ({subject_code})")
2683
2684        all_data = []
2685
2686        try:
2687            # 1. 导航到学科页面
2688            if not self.navigate_to_subject_page(subject_code):
2689                logging.error(f"无法访问学科页面: {subject_name}")
2690                return []
2691
2692            # 2. 获取总页数
2693            total_pages = self.get_total_pages()
2694            logging.info(f"总页数: {total_pages}")
2695
2696            # 3. 限制爬取的页数
2697            if max_pages and max_pages < total_pages:
2698                total_pages = max_pages
2699
2700            # 4. 爬取每一页数据
2701            for page_num in range(1, total_pages + 1):
2702                try:
2703                    logging.info(f"爬取第 {page_num}/{total_pages} 页...")
2704
2705                    # 如果是第一页，已经加载过了
2706                    if page_num > 1:
2707                        if not self.go_to_page(page_num):
2708                            logging.warning(f"无法跳转到第 {page_num} 页，跳过")
2709                            continue
2710
2711                    # 等待表格数据加载
2712                    table = self.wait_for_element(By.CLASS_NAME, "rk-table", timeout=10)
2713                    if not table:
2714                        logging.warning(f"第 {page_num} 页未找到表格")
2715                        continue
2716
2717                    # 等待表格有数据
2718                    time.sleep(2)
2719
2720                    # 解析当前页面数据
2721                    page_data = self.parse_current_page(subject_code, subject_name, page_num)
2722
2723                    if page_data:
2724                        all_data.extend(page_data)
2725                        logging.info(f"第 {page_num} 页解析到 {len(page_data)} 条数据")
2726
2727                        # 显示样本数据
2728                        if page_num <= 2:
2729                            logging.info(f"  样本数据:")
2730                            for i, data in enumerate(page_data[:2]):
2731                                logging.info(
2732                                    f"    排名2025:{data['ranking_position_2025']}, "
2733                                    f"排名2024:{data['ranking_position_2024']}, "
2734                                    f"{data['school_name']} - "
2735                                    f"分数: {data['score_2025']:.1f}")
2736                    else:
2737                        logging.warning(f"第 {page_num} 页未获取到数据")
2738                        # 尝试重新加载页面
2739                        if page_num == 1:
2740                            self.driver.refresh()
2741                            time.sleep(3)
2742
2743                    # 避免操作过于频繁
2744                    if page_num < total_pages:
2745                        delay = random.uniform(3, 6)
2746                        logging.info(f"  等待 {delay:.1f} 秒后继续...")
2747                        time.sleep(delay)
2748
2749                except Exception as e:
2750                    logging.error(f"爬取第 {page_num} 页失败: {e}")
2751                    # 尝试重新导航
2752                    if not self.navigate_to_subject_page(subject_code):
2753                        break
2754                    continue
2755
2756            if not all_data:
2757                logging.warning(f"学科 {subject_name} 未获取到任何数据")
2758                return []
2759
2760            # 5. 数据去重
2761            unique_data = {}
2762            for data in all_data:
2763                key = f"{data['ranking_position_2025']}_{data['school_name']}"
2764                if key not in unique_data:
2765                    unique_data[key] = data
2766
2767            all_data = list(unique_data.values())
2768
2769            # 6. 按排名排序
2770            all_data.sort(key=lambda x: x['ranking_position_2025'])
2771
2772            logging.info(f"学科 {subject_name} 爬取完成，共获取 {len(all_data)} 条唯一数据")
2773
2774            # 7. 显示前10条数据
2775            if all_data:
2776                logging.info(f"前10条数据:")
2777                for i, data in enumerate(all_data[:10]):
2778                    logging.info(
2779                        f"  排名2025:{data['ranking_position_2025']:3d}, "
2780                        f"排名2024:{data['ranking_position_2024']:3d}, "
2781                        f"{data['school_name']:20s} - "
2782                        f"分数: {data['score_2025']:.1f}")
2783
2784            return all_data
2785
2786        except Exception as e:
2787            logging.error(f"爬取学科排名失败 {subject_name}: {e}")
2788            return []
2789
2790    def save_subject_rankings_to_db(self, rankings):
2791        """保存学科排名数据到数据库"""
2792        if not rankings:
2793            logging.warning("没有学科排名数据可保存")
2794            return False
2795
2796        connection = self.get_db_connection()
2797        if not connection:
2798            return False
2799
2800        try:
2801            cursor = connection.cursor()
2802            saved_count = 0
2803            error_count = 0
2804
2805            for ranking in rankings:
2806                try:
2807                    if not ranking.get('school_name') or len(ranking['school_name']) < 2:
2808                        continue
2809
2810                    query = """
2811                    INSERT INTO shanghai_subject_rankings 
2812                    (year, subject_code, subject_name, ranking_position_2025, ranking_position_2024, 
2813                     school_name, score_2025, score_2024, indicator_scores_2025, indicator_scores_2024, 
2814                     subject_category, page_number)
2815                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
2816                    ON DUPLICATE KEY UPDATE
2817                    ranking_position_2025 = VALUES(ranking_position_2025),
2818                    ranking_position_2024 = VALUES(ranking_position_2024),
2819                    score_2025 = VALUES(score_2025),
2820                    score_2024 = VALUES(score_2024),
2821                    indicator_scores_2025 = VALUES(indicator_scores_2025),
2822                    indicator_scores_2024 = VALUES(indicator_scores_2024),
2823                    subject_category = VALUES(subject_category),
2824                    page_number = VALUES(page_number)
2825                    """
2826
2827                    cursor.execute(query, (
2828                        ranking['year'],
2829                        ranking['subject_code'],
2830                        ranking['subject_name'],
2831                        ranking['ranking_position_2025'],
2832                        ranking['ranking_position_2024'],
2833                        ranking['school_name'],
2834                        ranking['score_2025'],
2835                        ranking['score_2024'],
2836                        ranking['indicator_scores_2025'],
2837                        ranking['indicator_scores_2024'],
2838                        ranking['subject_category'],
2839                        ranking['page_number']
2840                    ))
2841                    saved_count += 1
2842
2843                except Error as e:
2844                    error_count += 1
2845                    logging.warning(
2846                        f"保存数据失败 {ranking.get('subject_name', '')}-{ranking.get('school_name', '')}: {e}")
2847                    continue
2848
2849            connection.commit()
2850            logging.info(f"成功保存 {saved_count} 条数据到数据库，失败 {error_count} 条")
2851            return True
2852
2853        except Error as e:
2854            logging.error(f"保存数据到数据库失败: {e}")
2855            connection.rollback()
2856            return False
2857        finally:
2858            if connection.is_connected():
2859                cursor.close()
2860                connection.close()
2861
2862    def test_single_subject(self, subject_code='0701', subject_name='数学', max_pages=3):
2863        """测试单个学科的爬取"""
2864        print(f"\n测试 {subject_name} 学科爬取 ({subject_code})")
2865        print(f"最大页数: {max_pages}")
2866
2867        data = self.fetch_subject_data(subject_code, subject_name, max_pages)
2868
2869        if data:
2870            print(f"\n测试完成，共获取 {len(data)} 条唯一数据")
2871            print(f"\n前10条数据:")
2872            for i, data_item in enumerate(data[:10]):
2873                print(f"  排名2025: {data_item['ranking_position_2025']:3d}, "
2874                      f"排名2024: {data_item['ranking_position_2024']:3d}, "
2875                      f"{data_item['school_name']:20s} - "
2876                      f"分数2025: {data_item['score_2025']:.1f} "
2877                      f"(第{data_item['page_number']}页)")
2878        else:
2879            print("未获取到数据")
2880
2881        return data
2882
2883    def test_pagination(self, subject_code='0701', subject_name='数学'):
2884        """测试分页有效性"""
2885        print(f"\n测试 {subject_name} 分页有效性 ({subject_code})")
2886
2887        try:
2888            # 导航到学科页面
2889            if not self.navigate_to_subject_page(subject_code):
2890                print("无法访问页面")
2891                return False
2892
2893            # 获取第一页数据
2894            print("获取第1页数据...")
2895            page1_data = self.parse_current_page(subject_code, subject_name, 1)
2896
2897            if not page1_data:
2898                print("无法获取第1页数据")
2899                return False
2900
2901            print(f"第1页获取到 {len(page1_data)} 条数据")
2902            if page1_data:
2903                print(f"第1页第一条: 排名2025:{page1_data[0]['ranking_position_2025']}, "
2904                      f"排名2024:{page1_data[0]['ranking_position_2024']}, "
2905                      f"{page1_data[0]['school_name']}")
2906
2907            # 尝试跳转到第2页
2908            print("\n尝试跳转到第2页...")
2909            if self.go_to_page(2):
2910                # 等待页面加载
2911                time.sleep(3)
2912
2913                # 获取第2页数据
2914                page2_data = self.parse_current_page(subject_code, subject_name, 2)
2915
2916                if page2_data:
2917                    print(f"第2页获取到 {len(page2_data)} 条数据")
2918                    if page2_data:
2919                        print(f"第2页第一条: 排名2025:{page2_data[0]['ranking_position_2025']}, "
2920                              f"排名2024:{page2_data[0]['ranking_position_2024']}, "
2921                              f"{page2_data[0]['school_name']}")
2922
2923                    # 比较数据
2924                    if page1_data and page2_data:
2925                        if (page1_data[0]['school_name'] == page2_data[0]['school_name']):
2926                            print("  ⚠ 警告：两页数据相同，分页可能无效！")
2927                            return False
2928                        else:
2929                            print("  ✓ 两页数据不同，分页成功！")
2930                            return True
2931                else:
2932                    print("无法获取第2页数据")
2933                    return False
2934            else:
2935                print("无法跳转到第2页")
2936                return False
2937
2938        except Exception as e:
2939            print(f"分页测试失败: {e}")
2940            return False
2941
2942    def export_to_excel(self):
2943        """导出数据到Excel"""
2944        print("\n导出数据到Excel...")
2945
2946        connection = self.get_db_connection()
2947        if not connection:
2948            print("数据库连接失败")
2949            return False
2950
2951        try:
2952            # 读取学科排名数据
2953            query = "SELECT * FROM shanghai_subject_rankings ORDER BY subject_code, ranking_position_2025"
2954            df = pd.read_sql(query, connection)
2955
2956            if df.empty:
2957                print("数据库中没有数据可导出")
2958                return False
2959
2960            # 创建导出目录
2961            export_dir = 'exports'
2962            if not os.path.exists(export_dir):
2963                os.makedirs(export_dir)
2964
2965            # 生成文件名
2966            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
2967            filename = f"shanghai_subject_rankings_{timestamp}.xlsx"
2968            filepath = os.path.join(export_dir, filename)
2969
2970            # 导出到Excel
2971            df.to_excel(filepath, index=False, engine='openpyxl')
2972            print(f"数据已导出到: {filepath}")
2973            print(f"共导出 {len(df)} 条记录")
2974            print(f"学科数量: {df['subject_code'].nunique()}")
2975            print(f"学校数量: {df['school_name'].nunique()}")
2976
2977            # 显示数据结构
2978            print("\n数据结构:")
2979            print(f"列名: {', '.join(df.columns.tolist())}")
2980
2981            # 显示前5条数据样本
2982            print("\n前5条数据样本:")
2983            for i, row in df.head().iterrows():
2984                print(f"  {row['subject_name']} - {row['school_name']}: "
2985                      f"排名2025:{row['ranking_position_2025']}, "
2986                      f"排名2024:{row['ranking_position_2024']}, "
2987                      f"分数2025:{row['score_2025']:.1f}")
2988
2989            return True
2990
2991        except Exception as e:
2992            print(f"导出数据失败: {e}")
2993            return False
2994        finally:
2995            if connection.is_connected():
2996                connection.close()
2997
2998    def clear_database(self):
2999        """清除数据库中的数据"""
3000        print("\n清除数据库中的数据...")
3001
3002        confirm = input("确认清除所有软科排名数据？此操作不可恢复！(输入 'yes' 确认): ").strip()
3003        if confirm.lower() != 'yes':
3004            print("已取消清除操作")
3005            return False
3006
3007        connection = self.get_db_connection()
3008        if not connection:
3009            print("数据库连接失败")
3010            return False
3011
3012        try:
3013            cursor = connection.cursor()
3014
3015            # 获取当前数据统计
3016            cursor.execute("SELECT COUNT(*) as count FROM shanghai_subject_rankings")
3017            subject_count = cursor.fetchone()[0]
3018
3019            print(f"当前学科排名表有 {subject_count} 条记录")
3020
3021            # 执行删除
3022            cursor.execute("DELETE FROM shanghai_subject_rankings")
3023            connection.commit()
3024
3025            print("数据清除成功")
3026            return True
3027
3028        except Error as e:
3029            print(f"清除数据失败: {e}")
3030            connection.rollback()
3031            return False
3032        finally:
3033            if connection.is_connected():
3034                cursor.close()
3035                connection.close()
3036
3037    def close_driver(self):
3038        """关闭WebDriver"""
3039        if self.driver:
3040            try:
3041                self.driver.quit()
3042                logging.info("WebDriver已关闭")
3043            except:
3044                pass
3045
3046
3047def get_db_connection():
3048    """获取数据库连接"""
3049    try:
3050        connection = pymysql.connect(
3051            host='localhost',
3052            user='root',
3053            password='Wza!64416685',
3054            database='kaoyan_data',
3055            charset='utf8mb4',
3056            cursorclass=DictCursor
3057        )
3058        return connection
3059    except Error as e:
3060        st.error(f"数据库连接失败: {e}")
3061        return None
3062
3063
3064def init_database():
3065    """初始化数据库表"""
3066    connection = get_db_connection()
3067    if not connection:
3068        return False
3069
3070    try:
3071        with connection.cursor() as cursor:
3072            # 创建用户表
3073            cursor.execute("""
3074                CREATE TABLE IF NOT EXISTS users (
3075                    id INT AUTO_INCREMENT PRIMARY KEY,
3076                    username VARCHAR(50) UNIQUE NOT NULL,
3077                    email VARCHAR(100) UNIQUE NOT NULL,
3078                    password_hash VARCHAR(255) NOT NULL,
3079                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
3080                    last_login TIMESTAMP NULL,
3081                    is_active BOOLEAN DEFAULT TRUE
3082                )
3083            """)
3084
3085            # 创建聊天记录表
3086            cursor.execute("""
3087                CREATE TABLE IF NOT EXISTS chat_history (
3088                    id INT AUTO_INCREMENT PRIMARY KEY,
3089                    user_id INT,
3090                    question TEXT NOT NULL,
3091                    answer TEXT NOT NULL,
3092                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
3093                    FOREIGN KEY (user_id) REFERENCES users(id)
3094                )
3095            """)
3096
3097        connection.commit()
3098        return True
3099    except Error as e:
3100        st.error(f"数据库初始化失败: {e}")
3101        return False
3102    finally:
3103        connection.close()
3104
3105
3106def hash_password(password):
3107    """密码哈希处理"""
3108    return hashlib.sha256(password.encode()).hexdigest()
3109
3110
3111def validate_email(email):
3112    """验证邮箱格式"""
3113    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
3114    return re.match(pattern, email) is not None
3115
3116
3117def validate_username(username):
3118    """验证用户名格式"""
3119    return len(username) >= 3 and len(username) <= 50 and re.match(r'^[a-zA-Z0-9_]+$', username)
3120
3121
3122def register_user(username, email, password):
3123    """注册新用户"""
3124    connection = get_db_connection()
3125    if not connection:
3126        return False, "数据库连接失败"
3127
3128    try:
3129        with connection.cursor() as cursor:
3130            # 检查用户名是否已存在
3131            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
3132            if cursor.fetchone():
3133                return False, "用户名已存在"
3134
3135            # 检查邮箱是否已存在
3136            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
3137            if cursor.fetchone():
3138                return False, "邮箱已被注册"
3139
3140            # 插入新用户
3141            password_hash = hash_password(password)
3142            cursor.execute(
3143                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
3144                (username, email, password_hash)
3145            )
3146
3147        connection.commit()
3148        return True, "注册成功"
3149
3150    except Error as e:
3151        return False, f"注册失败: {str(e)}"
3152    finally:
3153        connection.close()
3154
3155
3156def verify_user(username, password):
3157    """验证用户登录"""
3158    connection = get_db_connection()
3159    if not connection:
3160        return False, None
3161
3162    try:
3163        with connection.cursor() as cursor:
3164            password_hash = hash_password(password)
3165
3166            cursor.execute(
3167                "SELECT id, username, email FROM users WHERE username = %s AND password_hash = %s AND is_active = TRUE",
3168                (username, password_hash)
3169            )
3170
3171            user = cursor.fetchone()
3172            if user:
3173                # 更新最后登录时间
3174                cursor.execute(
3175                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s",
3176                    (user['id'],)
3177                )
3178                connection.commit()
3179                return True, user
3180            else:
3181                return False, None
3182
3183    except Error as e:
3184        return False, None
3185    finally:
3186        connection.close()
3187
3188
3189def save_chat_history(user_id, question, answer):
3190    """保存聊天记录到数据库"""
3191    connection = get_db_connection()
3192    if not connection:
3193        return False
3194
3195    try:
3196        with connection.cursor() as cursor:
3197            cursor.execute(
3198                "INSERT INTO chat_history (user_id, question, answer) VALUES (%s, %s, %s)",
3199                (user_id, question, answer)
3200            )
3201        connection.commit()
3202        return True
3203    except Error:
3204        return False
3205    finally:
3206        connection.close()
3207
3208
3209def get_chat_history(user_id, limit=10):
3210    """获取用户聊天记录"""
3211    connection = get_db_connection()
3212    if not connection:
3213        return []
3214
3215    try:
3216        with connection.cursor() as cursor:
3217            cursor.execute(
3218                "SELECT question, answer, timestamp FROM chat_history WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
3219                (user_id, limit)
3220            )
3221            return cursor.fetchall()
3222    except Error:
3223        return []
3224    finally:
3225        connection.close()
3226
3227
3228def query_database(question):
3229    """根据问题精确查询考研数据库"""
3230    connection = get_db_connection()
3231    if not connection:
3232        return []
3233
3234    try:
3235        with connection.cursor() as cursor:
3236            # 1. 提取关键词进行精确查询
3237            question_lower = question.lower()
3238
3239            # 动态构建查询条件
3240            conditions = []
3241            params = []
3242
3243            # 提取学校名：尝试匹配"XX大学"格式
3244            import re
3245            school_pattern = r'([\u4e00-\u9fa5]+大学)'
3246            school_matches = re.findall(school_pattern, question)
3247
3248            if school_matches:
3249                for school in school_matches:
3250                    conditions.append("school_name LIKE %s")
3251                    params.append(f"%{school}%")
3252
3253            # 提取专业名：常见专业关键词
3254            major_patterns = [
3255                '信息安全', '计算机', '软件', '人工智能', '电子信息',
3256                '电子科学', '网络空间安全', '电子信息技术', '新一代电子信息技术',
3257                '计算机科学与技术', '软件工程', '人工智能', '网络安全'
3258            ]
3259
3260            for pattern in major_patterns:
3261                if pattern in question:
3262                    conditions.append("major_name LIKE %s")
3263                    params.append(f"%{pattern}%")
3264
3265            # 提取研究方向关键词
3266            direction_keywords = ['方向', '研究方向', '有哪些方向', '什么方向']
3267            has_direction_query = any(keyword in question for keyword in direction_keywords)
3268
3269            # 构建查询SQL
3270            if conditions:
3271                query = """
3272                SELECT DISTINCT 
3273                    school_name, major_name, major_code, department, research_direction,
3274                    politics_subject, foreign_language_subject, business_subject1, business_subject2,
3275                    enrollment_plan, region, data_source
3276                FROM exam_subjects 
3277                WHERE """ + " OR ".join(conditions)
3278
3279                # 如果是询问方向，优先返回有明确研究方向的数据
3280                if has_direction_query:
3281                    query += " AND research_direction IS NOT NULL AND research_direction != ''"
3282
3283                query += " ORDER BY school_name, major_name, research_direction"
3284                cursor.execute(query, params)
3285            else:
3286                # 如果没有匹配条件，使用智能匹配
3287                words = question.replace('?', '').replace('？', '').split()
3288                if len(words) > 0:
3289                    query = """
3290                    SELECT * FROM exam_subjects 
3291                    WHERE CONCAT(school_name, major_name, research_direction) LIKE %s
3292                    ORDER BY school_name, major_name
3293                    LIMIT 10
3294                    """
3295                    search_term = f"%{'%'.join(words)}%"
3296                    cursor.execute(query, (search_term,))
3297                else:
3298                    return []
3299
3300            results = cursor.fetchall()
3301
3302            # 2. 对结果进行智能分组（同一学校+专业的方向合并）
3303            grouped_results = []
3304            seen = {}
3305
3306            for result in results:
3307                key = f"{result['school_name']}_{result['major_name']}"
3308
3309                if key not in seen:
3310                    seen[key] = {
3311                        'school_name': result['school_name'],
3312                        'major_name': result['major_name'],
3313                        'major_code': result.get('major_code', ''),
3314                        'research_directions': [],
3315                        'departments': set(),
3316                        'enrollment_plan': result.get('enrollment_plan', ''),
3317                        'politics_subject': result.get('politics_subject', ''),
3318                        'foreign_language_subject': result.get('foreign_language_subject', ''),
3319                        'business_subject1': result.get('business_subject1', ''),
3320                        'business_subject2': result.get('business_subject2', ''),
3321                        'region': result.get('region', ''),
3322                        'data_source': result.get('data_source', '')
3323                    }
3324
3325                # 添加研究方向（去重）
3326                if result.get('research_direction'):
3327                    direction = result['research_direction'].strip()
3328                    if direction and direction not in seen[key]['research_directions']:
3329                        seen[key]['research_directions'].append(direction)
3330
3331                # 添加院系信息（去重）
3332                if result.get('department'):
3333                    seen[key]['departments'].add(result['department'])
3334
3335            # 转换为列表格式
3336            for key, value in seen.items():
3337                value['departments'] = list(value['departments'])
3338                grouped_results.append(value)
3339
3340            return grouped_results
3341
3342    except Error as e:
3343        print(f"数据库查询错误: {e}")
3344        return []
3345    finally:
3346        connection.close()
3347
3348
3349def format_database_results(results):
3350    """格式化数据库查询结果，优化回答结构"""
3351    if not results:
3352        return "未在数据库中查询到相关信息。"
3353
3354    formatted = "以下是数据库中的相关考研信息：\n\n"
3355
3356    for i, result in enumerate(results, 1):
3357        formatted += f"**{i}. {result['school_name']} - {result['major_name']}**"
3358
3359        if result.get('major_code'):
3360            formatted += f"（{result['major_code']}）"
3361        formatted += "\n"
3362
3363        # 显示研究方向（重点）
3364        if result.get('research_directions'):
3365            formatted += "   **研究方向**：\n"
3366            for direction in result['research_directions']:
3367                formatted += f"   - {direction}\n"
3368        else:
3369            formatted += "   **研究方向**：数据库中未记录具体方向，或该专业在招生时不区分方向。\n"
3370
3371        # 显示院系信息
3372        if result.get('departments'):
3373            formatted += f"   **开设院系**：{', '.join(result['departments'])}\n"
3374
3375        # 显示招生信息（如有）
3376        if result.get('enrollment_plan'):
3377            formatted += f"   **拟招生人数**：{result['enrollment_plan']}\n"
3378
3379        # 显示考试科目（如有）
3380        has_exam_subjects = (
3381                result.get('politics_subject') or
3382                result.get('foreign_language_subject') or
3383                result.get('business_subject1') or
3384                result.get('business_subject2')
3385        )
3386
3387        if has_exam_subjects:
3388            formatted += "   **考试科目**：\n"
3389            if result.get('politics_subject'):
3390                formatted += f"   - 政治：{result['politics_subject']}\n"
3391            if result.get('foreign_language_subject'):
3392                formatted += f"   - 外语：{result['foreign_language_subject']}\n"
3393            if result.get('business_subject1'):
3394                formatted += f"   - 业务课一：{result['business_subject1']}\n"
3395            if result.get('business_subject2'):
3396                formatted += f"   - 业务课二：{result['business_subject2']}\n"
3397
3398        formatted += f"   **地区**：{result.get('region', '未记录')}\n"
3399        formatted += "\n"
3400
3401    # 添加重要的说明信息
3402    formatted += """
3403---
3404**重要说明**：
34051. 以上信息基于数据库中的历史招生数据，实际招生信息请以学校官方最新公布为准。
34062. "不区分方向"在官方文件中通常指复试分数线统一，但入学后实际研究会有具体方向划分。
34073. 同一专业在不同院系可能开设不同研究方向。
3408"""
3409
3410    return formatted
3411
3412
3413def call_deepseek_api(question, context):
3414    """调用DeepSeek API，优化提示词和回答生成"""
3415    try:
3416        api_key = st.secrets.get("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
3417        url = "https://api.deepseek.com/v1/chat/completions"
3418
3419        headers = {
3420            "Content-Type": "application/json",
3421            "Authorization": f"Bearer {api_key}"
3422        }
3423
3424        # 优化系统提示词，强调基于数据库回答
3425        system_prompt = """你是一个专业的考研咨询助手，请严格按照提供的数据库信息回答问题。
3426
3427**回答准则**：
34281. **忠实于数据库**：所有回答必须基于提供的数据库信息，不添加未提及的信息。
34292. **解释说明**：如果数据库信息与常见认知有差异（如"不区分方向"），请基于数据库信息解释。
34303. **结构清晰**：按学校、专业、研究方向、考试科目的顺序组织回答。
34314. **完整性**：列出数据库中所有相关信息，不遗漏。
34325. **客观性**：不添加主观评价，只陈述事实。
3433
3434**特别注意事项**：
3435- 当数据库显示多个研究方向时，全部列出。
3436- 当数据库显示"不区分研究方向"时，如实说明，并解释这通常指复试时统一分数线。
3437- 如果数据库没有相关信息，明确说明。
3438"""
3439
3440        # 优化用户消息格式
3441        user_message = f"""用户问题：{question}
3442
3443数据库查询结果：
3444{context}
3445
3446请根据以上数据库信息回答用户问题。注意：
34471. 如果数据库中有多条记录，请汇总整理后回答。
34482. 如果研究方向为空或显示"不区分研究方向"，请说明实际情况。
34493. 如果数据库信息不全，请说明哪些信息缺失。
34504. 回答要简洁、准确、完整。
3451"""
3452
3453        data = {
3454            "model": "deepseek-chat",
3455            "messages": [
3456                {"role": "system", "content": system_prompt},
3457                {"role": "user", "content": user_message}
3458            ],
3459            "temperature": 0.3,  # 降低随机性，提高确定性
3460            "max_tokens": 2500
3461        }
3462
3463        response = requests.post(url, headers=headers, json=data, timeout=30)
3464
3465        if response.status_code == 200:
3466            result = response.json()
3467            answer = result['choices'][0]['message']['content']
3468
3469            # 后处理：确保回答基于数据库
3470            if "未在数据库中" in context and "未找到" not in answer.lower():
3471                answer += "\n\n注：以上信息基于数据库查询结果，如与官方信息有出入，请以学校官方发布为准。"
3472
3473            return answer
3474        else:
3475            return f"AI服务暂时不可用，状态码：{response.status_code}\n\n数据库查询结果：\n{context}"
3476
3477    except Exception as e:
3478        return f"调用AI服务时出错：{str(e)}\n\n数据库查询结果：\n{context}"
3479
3480
3481def get_school_list():
3482    """获取学校列表"""
3483    connection = get_db_connection()
3484    if not connection:
3485        return []
3486
3487    try:
3488        with connection.cursor() as cursor:
3489            cursor.execute("SELECT DISTINCT school_name FROM exam_subjects ORDER BY school_name")
3490            schools = [row['school_name'] for row in cursor.fetchall()]
3491            return schools
3492    except Error:
3493        return []
3494    finally:
3495        connection.close()
3496
3497
3498def login_page():
3499    """登录页面"""
3500    st.title("🎓 考研AI问答系统 - 登录")
3501
3502    with st.form("login_form"):
3503        username = st.text_input("用户名", placeholder="请输入用户名")
3504        password = st.text_input("密码", type="password", placeholder="请输入密码")
3505        submit = st.form_submit_button("登录")
3506
3507        if submit:
3508            if not username or not password:
3509                st.error("请输入用户名和密码")
3510            else:
3511                success, user = verify_user(username, password)
3512                if success:
3513                    st.session_state.user = user
3514                    st.session_state.page = "main"
3515                    st.rerun()
3516                else:
3517                    st.error("用户名或密码错误")
3518
3519    st.markdown("---")
3520    st.write("还没有账号？")
3521    if st.button("立即注册"):
3522        st.session_state.page = "register"
3523        st.rerun()
3524
3525
3526def register_page():
3527    """注册页面"""
3528    st.title("🎓 考研AI问答系统 - 注册")
3529
3530    with st.form("register_form"):
3531        username = st.text_input("用户名", placeholder="3-50个字符，只能包含字母、数字和下划线")
3532        email = st.text_input("邮箱", placeholder="请输入有效的邮箱地址")
3533        password = st.text_input("密码", type="password", placeholder="请输入密码")
3534        confirm_password = st.text_input("确认密码", type="password", placeholder="请再次输入密码")
3535        submit = st.form_submit_button("注册")
3536
3537        if submit:
3538            # 验证输入
3539            if not username or not email or not password:
3540                st.error("请填写所有字段")
3541            elif not validate_username(username):
3542                st.error("用户名格式不正确（3-50个字符，只能包含字母、数字和下划线）")
3543            elif not validate_email(email):
3544                st.error("邮箱格式不正确")
3545            elif password != confirm_password:
3546                st.error("两次输入的密码不一致")
3547            elif len(password) < 6:
3548                st.error("密码长度至少6位")
3549            else:
3550                success, message = register_user(username, email, password)
3551                if success:
3552                    st.success(message)
3553                    st.info("请返回登录页面登录")
3554                else:
3555                    st.error(message)
3556
3557    st.markdown("---")
3558    st.write("已有账号？")
3559    if st.button("返回登录"):
3560        st.session_state.page = "login"
3561        st.rerun()
3562
3563
3564def main_page():
3565    """主页面 - AI问答（优化版）"""
3566    st.title("🤖 考研AI智能问答")
3567
3568    # 用户信息栏
3569    col1, col2, col3 = st.columns([3, 1, 1])
3570    with col1:
3571        st.write(f"欢迎，**{st.session_state.user['username']}**！")
3572    with col2:
3573        if st.button("📊 数据查询"):
3574            st.session_state.page = "data_query"
3575            st.rerun()
3576    with col3:
3577        if st.button("🚪 退出登录"):
3578            st.session_state.clear()
3579            st.rerun()
3580
3581    st.markdown("---")
3582
3583    # 初始化聊天历史
3584    if 'messages' not in st.session_state:
3585        st.session_state.messages = []
3586        history = get_chat_history(st.session_state.user['id'])
3587        for item in history:
3588            st.session_state.messages.append({"role": "user", "content": item['question']})
3589            st.session_state.messages.append({"role": "assistant", "content": item['answer']})
3590
3591    # 显示聊天记录
3592    for message in st.session_state.messages:
3593        with st.chat_message(message["role"]):
3594            st.markdown(message["content"])
3595
3596    # 优化示例问题
3597    st.subheader("💡 示例问题：")
3598    examples = [
3599        "中国地质大学信息安全专业有哪些研究方向？",
3600        "浙江大学计算机科学与技术专业的考试科目是什么？",
3601        "厦门大学电子信息专业招生多少人？",
3602        "北京地区有哪些高校开设计算机相关专业？"
3603    ]
3604
3605    cols = st.columns(4)
3606    for i, example in enumerate(examples):
3607        with cols[i]:
3608            if st.button(example[:15] + "..." if len(example) > 15 else example, key=f"example_{i}"):
3609                st.session_state.new_question = example
3610
3611    # 聊天输入
3612    question = st.text_area(
3613        "请输入您的问题：",
3614        value=st.session_state.get('new_question', ''),
3615        height=100,
3616        placeholder="例如：中国地质大学信息安全专业有哪些研究方向？"
3617    )
3618
3619    col1, col2 = st.columns([4, 1])
3620    with col1:
3621        if st.button("🔍 获取答案", type="primary", use_container_width=True):
3622            if question:
3623                # 添加用户消息
3624                st.session_state.messages.append({"role": "user", "content": question})
3625
3626                # 显示用户消息
3627                with st.chat_message("user"):
3628                    st.markdown(question)
3629
3630                # 生成AI回复
3631                with st.chat_message("assistant"):
3632                    with st.spinner("正在查询数据库并生成回答..."):
3633                        # 查询数据库
3634                        db_results = query_database(question)
3635                        context = format_database_results(db_results)
3636
3637                        # 显示数据库查询结果（可折叠）
3638                        with st.expander("查看数据库原始查询结果", expanded=False):
3639                            if db_results:
3640                                df = pd.DataFrame(db_results)
3641                                # 简化显示列
3642                                display_cols = ['school_name', 'major_name', 'research_directions', 'departments']
3643                                display_df = df[display_cols] if all(col in df.columns for col in display_cols) else df
3644                                st.dataframe(display_df)
3645                            else:
3646                                st.info("数据库未查询到相关记录")
3647
3648                        # 调用AI API
3649                        response = call_deepseek_api(question, context)
3650
3651                        # 显示回答
3652                        st.markdown(response)
3653
3654                        # 保存到数据库
3655                        save_chat_history(st.session_state.user['id'], question, response)
3656
3657                # 添加助手消息
3658                st.session_state.messages.append({"role": "assistant", "content": response})
3659
3660                # 清空问题
3661                if 'new_question' in st.session_state:
3662                    del st.session_state.new_question
3663            else:
3664                st.warning("请输入问题")
3665    with col2:
3666        if st.button("清空对话"):
3667            st.session_state.messages = []
3668            st.rerun()
3669
3670
3671def data_query_page():
3672    """数据查询页面"""
3673    st.title("📚 考研数据查询")
3674
3675    col1, col2, col3 = st.columns([3, 1, 1])
3676    with col1:
3677        st.write(f"欢迎，**{st.session_state.user['username']}**！")
3678    with col2:
3679        if st.button("🤖 AI问答"):
3680            st.session_state.page = "main"
3681            st.rerun()
3682    with col3:
3683        if st.button("🚪 退出登录"):
3684            st.session_state.clear()
3685            st.rerun()
3686
3687    st.markdown("---")
3688
3689    # 查询选项
3690    tab1, tab2, tab3 = st.tabs(["🔍 条件查询", "🏫 学校浏览", "📊 数据统计"])
3691
3692    with tab1:
3693        st.subheader("条件查询")
3694        col1, col2 = st.columns(2)
3695        with col1:
3696            school_name = st.text_input("学校名称", key="query_school")
3697        with col2:
3698            major_name = st.text_input("专业名称", key="query_major")
3699
3700        if st.button("查询", key="query_btn"):
3701            if school_name or major_name:
3702                connection = get_db_connection()
3703                if connection:
3704                    try:
3705                        with connection.cursor() as cursor:
3706                            query = "SELECT * FROM exam_subjects WHERE 1=1"
3707                            params = []
3708
3709                            if school_name:
3710                                query += " AND school_name LIKE %s"
3711                                params.append(f"%{school_name}%")
3712                            if major_name:
3713                                query += " AND major_name LIKE %s"
3714                                params.append(f"%{major_name}%")
3715
3716                            query += " ORDER BY school_name, major_name LIMIT 50"
3717                            cursor.execute(query, params)
3718                            results = cursor.fetchall()
3719
3720                            if results:
3721                                st.subheader(f"找到 {len(results)} 条结果")
3722                                for result in results:
3723                                    with st.expander(f"{result['school_name']} - {result['major_name']}"):
3724                                        col1, col2 = st.columns(2)
3725                                        with col1:
3726                                            st.write("**基本信息**")
3727                                            st.write(f"专业代码：{result.get('major_code', '')}")
3728                                            st.write(f"院系：{result.get('department', '')}")
3729                                            st.write(f"研究方向：{result.get('research_direction', '')}")
3730                                            st.write(f"招生人数：{result.get('enrollment_plan', '')}")
3731                                            st.write(f"地区：{result.get('region', '')}")
3732
3733                                        with col2:
3734                                            st.write("**考试科目**")
3735                                            if result.get('politics_subject'):
3736                                                st.write(f"政治：{result['politics_subject']}")
3737                                            if result.get('foreign_language_subject'):
3738                                                st.write(f"外语：{result['foreign_language_subject']}")
3739                                            if result.get('business_subject1'):
3740                                                st.write(f"业务课一：{result['business_subject1']}")
3741                                            if result.get('business_subject2'):
3742                                                st.write(f"业务课二：{result['business_subject2']}")
3743
3744                                        if result.get('exam_scope'):
3745                                            st.write(f"**考试范围：** {result['exam_scope']}")
3746
3747                                        if result.get('reference_books'):
3748                                            st.write(f"**参考书籍：** {result['reference_books']}")
3749                            else:
3750                                st.warning("未找到相关数据")
3751
3752                    except Error as e:
3753                        st.error(f"查询失败: {e}")
3754                    finally:
3755                        connection.close()
3756            else:
3757                st.warning("请输入至少一个查询条件")
3758
3759    with tab2:
3760        st.subheader("学校专业浏览")
3761        schools = get_school_list()
3762
3763        if schools:
3764            selected_school = st.selectbox("选择学校", schools, key="browse_school")
3765
3766            if selected_school:
3767                connection = get_db_connection()
3768                if connection:
3769                    try:
3770                        with connection.cursor() as cursor:
3771                            cursor.execute(
3772                                "SELECT DISTINCT major_name FROM exam_subjects WHERE school_name = %s ORDER BY major_name",
3773                                (selected_school,)
3774                            )
3775                            majors = [row['major_name'] for row in cursor.fetchall()]
3776
3777                            if majors:
3778                                selected_major = st.selectbox("选择专业", majors, key="browse_major")
3779
3780                                if selected_major:
3781                                    cursor.execute(
3782                                        "SELECT * FROM exam_subjects WHERE school_name = %s AND major_name = %s ORDER BY department",
3783                                        (selected_school, selected_major)
3784                                    )
3785                                    results = cursor.fetchall()
3786
3787                                    if results:
3788                                        for result in results:
3789                                            with st.expander(
3790                                                    f"{result['department']} - {result.get('research_direction', '不区分研究方向')}"):
3791                                                col1, col2 = st.columns(2)
3792                                                with col1:
3793                                                    st.write("**基本信息**")
3794                                                    st.write(f"专业代码：{result.get('major_code', '')}")
3795                                                    st.write(f"招生人数：{result.get('enrollment_plan', '')}")
3796
3797                                                with col2:
3798                                                    st.write("**考试科目**")
3799                                                    if result.get('politics_subject'):
3800                                                        st.write(f"政治：{result['politics_subject']}")
3801                                                    if result.get('foreign_language_subject'):
3802                                                        st.write(f"外语：{result['foreign_language_subject']}")
3803                                                    if result.get('business_subject1'):
3804                                                        st.write(f"业务课一：{result['business_subject1']}")
3805                                                    if result.get('business_subject2'):
3806                                                        st.write(f"业务课二：{result['business_subject2']}")
3807                            else:
3808                                st.warning("该学校暂无专业信息")
3809
3810                    except Error as e:
3811                        st.error(f"查询失败: {e}")
3812                    finally:
3813                        connection.close()
3814        else:
3815            st.warning("暂无学校数据")
3816
3817    with tab3:
3818        st.subheader("数据统计")
3819        connection = get_db_connection()
3820        if connection:
3821            try:
3822                with connection.cursor() as cursor:
3823                    # 基本统计
3824                    col1, col2, col3 = st.columns(3)
3825
3826                    with col1:
3827                        cursor.execute("SELECT COUNT(*) FROM exam_subjects")
3828                        total_records = cursor.fetchone()['COUNT(*)']
3829                        st.metric("总记录数", total_records)
3830
3831                    with col2:
3832                        cursor.execute("SELECT COUNT(DISTINCT school_name) FROM exam_subjects")
3833                        total_schools = cursor.fetchone()['COUNT(DISTINCT school_name)']
3834                        st.metric("覆盖高校数", total_schools)
3835
3836                    with col3:
3837                        cursor.execute("SELECT COUNT(DISTINCT major_name) FROM exam_subjects")
3838                        total_majors = cursor.fetchone()['COUNT(DISTINCT major_name)']
3839                        st.metric("专业数量", total_majors)
3840
3841                    # 热门专业
3842                    st.subheader("热门专业TOP 10")
3843                    cursor.execute("""
3844                        SELECT major_name, COUNT(*) as count 
3845                        FROM exam_subjects 
3846                        GROUP BY major_name 
3847                        ORDER BY count DESC 
3848                        LIMIT 10
3849                    """)
3850                    major_stats = cursor.fetchall()
3851
3852                    if major_stats:
3853                        df_major = pd.DataFrame(major_stats)
3854                        st.dataframe(df_major, use_container_width=True)
3855
3856                    # 地区分布
3857                    st.subheader("地区分布")
3858                    cursor.execute(
3859                        "SELECT region, COUNT(*) as count FROM exam_subjects GROUP BY region ORDER BY count DESC")
3860                    region_stats = cursor.fetchall()
3861
3862                    if region_stats:
3863                        df_region = pd.DataFrame(region_stats)
3864                        st.bar_chart(df_region.set_index('region'))
3865
3866            except Error as e:
3867                st.error(f"获取统计信息失败: {e}")
3868            finally:
3869                connection.close()
3870
3871
3872def main():
3873    """主函数"""
3874    # 检查MySQL是否可用
3875    if 'MYSQL_AVAILABLE' not in globals():
3876        global MYSQL_AVAILABLE
3877        MYSQL_AVAILABLE = True
3878
3879    # 初始化数据库
3880    if 'db_initialized' not in st.session_state:
3881        if init_database():
3882            st.session_state.db_initialized = True
3883        else:
3884            st.error("数据库初始化失败，请检查数据库连接")
3885            return
3886
3887    # 页面路由
3888    if 'page' not in st.session_state:
3889        st.session_state.page = "login"
3890
3891    # 根据当前页面显示相应内容
3892    if st.session_state.page == "login":
3893        login_page()
3894    elif st.session_state.page == "register":
3895        register_page()
3896    elif st.session_state.page == "main":
3897        if 'user' in st.session_state:
3898            main_page()
3899        else:
3900            st.session_state.page = "login"
3901            st.rerun()
3902    elif st.session_state.page == "data_query":
3903        if 'user' in st.session_state:
3904            data_query_page()
3905        else:
3906            st.session_state.page = "login"
3907            st.rerun()
3908
3909
3910if __name__ == "__main__":
3911    main()
3912
```