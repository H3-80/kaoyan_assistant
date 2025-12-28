# 🎓 考研AI问答与数据分析系统

> 一个集数据采集、智能问答、数据可视化于一体的端到端考研信息系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📖 目录
- [项目简介](#项目简介)
- [✨ 功能特性](#-功能特性)
- [🏗️ 系统架构](#️-系统架构)
- [🚀 快速开始](#-快速开始)
  - [环境要求](#环境要求)
  - [安装步骤](#安装步骤)
  - [配置说明](#配置说明)
- [📊 数据库设计](#-数据库设计)
- [🖥️ 使用说明](#️-使用说明)
  - [数据采集](#数据采集)
  - [Web应用](#web应用)
- [🔧 项目结构](#-项目结构)
- [🤖 AI使用说明](#-ai使用说明)
- [📈 数据统计](#-数据统计)
- [🎯 核心查询示例](#-核心查询示例)
- [⚠️ 注意事项](#️-注意事项)

## 项目简介

随着考研竞争日益激烈，考生对院校专业信息的准确性和全面性需求不断增加。本项目旨在构建一个**集数据采集、智能问答、数据可视化于一体的端到端考研信息系统**，帮助考生快速获取准确的考研信息。

系统整合了：
1. **中国研究生招生信息网**的官方招生数据（包括学校、专业、研究方向、考试科目、招生人数等）
2. **软科排名网站**的学科评估数据（2024-2025年学科排名）
3. **DeepSeek大语言模型**的智能问答能力

通过多线程爬虫采集数据，存储在MySQL数据库，并通过Streamlit Web界面提供智能问答和数据查询服务。

## ✨ 功能特性

### 📥 数据采集
- **多线程爬虫**：支持并发爬取，提高数据采集效率
- **智能容错**：自动重试、浏览器重启、异常处理机制
- **数据去重**：基于唯一键自动去重，保证数据质量
- **断点续传**：记录爬取进度，支持中断后继续爬取
- **动态学科获取**：软科排名爬虫动态获取最新学科列表

### 🗄️ 数据存储
- **结构化存储**：MySQL关系型数据库，支持复杂查询
- **数据关联**：考研信息与学科排名数据关联查询
- **用户数据**：完整的用户系统和聊天历史记录
- **双数据源**：研招网考试科目 + 软科学科排名

### 🤖 智能问答
- **AI驱动**：基于DeepSeek大语言模型的智能问答
- **数据准确**：所有回答均基于数据库真实数据
- **智能解析**：自动识别问题中的学校、专业关键词
- **混合查询**：同时查询考试科目和学科排名信息
- **实时预览**：可查看AI回答背后的原始数据库结果

### 📊 数据可视化
- **条件查询**：多字段组合查询，支持模糊匹配
- **统计分析**：专业热度、地区分布等数据统计
- **排名查询**：软科学科排名查询与可视化展示
- **数据浏览**：按学校、专业分层浏览

### 👤 用户系统
- **安全认证**：用户注册、登录、密码哈希存储
- **历史记录**：保存用户问答历史，支持查看和清空
- **邮箱登录**：支持邮箱作为登录凭证
- **会话管理**：安全的用户会话状态管理

### 🔧 交互式界面
- **双模式运行**：支持命令行交互和Web界面
- **实时进度**：爬虫运行状态实时显示
- **批量操作**：支持批量爬取、批量删除
- **智能提醒**：数据已存在时的智能处理提示

## 🏗️ 系统架构

```
考研AI问答系统
├── 数据采集层
│   ├── 研招网爬虫 (ThreadSafeSpider + CompleteInfoSpider)
│   │   ├── 多线程爬取
│   │   ├── 智能重试
│   │   └── 数据清洗
│   └── 软科排名爬虫 (ShanghaiRankingSpider)
│       ├── 动态学科获取
│       ├── 分页处理
│       └── 排名解析
├── 数据存储层
│   ├── MySQL数据库（5个核心表）
│   ├── 数据持久化
│   └── 数据关联
├── 业务逻辑层
│   ├── 用户认证系统
│   ├── 数据查询引擎
│   ├── AI问答引擎（DeepSeek集成）
│   └── 数据统计模块
└── 表现层
    ├── Streamlit Web界面（登录/注册/问答/查询）
    ├── 命令行交互界面（爬虫管理）
    └── 响应式数据展示
```

## 🚀 快速开始

### 环境要求

- **Python**: 3.8 或更高版本
- **MySQL**: 8.0 或更高版本
- **Edge浏览器**: 最新版本（用于Selenium爬虫）
- **操作系统**: Windows 10/11（推荐）或 Linux/macOS
- **内存**: 建议8GB以上
- **磁盘空间**: 至少2GB可用空间

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/H3-80/kaoyan_assistant.git
   cd kaoyan_assistant
   ```

2. **安装Python依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置MySQL数据库**
   ```sql
   -- 创建数据库
   CREATE DATABASE kaoyan_data CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   
   -- 创建用户并授权
   CREATE USER 'kaoyan_user'@'localhost' IDENTIFIED BY 'your_password';
   GRANT ALL PRIVILEGES ON kaoyan_data.* TO 'kaoyan_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

4. **下载Edge浏览器驱动**
   - 访问 https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/
   - 下载与你的Edge浏览器版本匹配的驱动
   - 将`msedgedriver.exe`放置在项目根目录或指定路径

### 配置说明

1. **数据库配置**
   在代码中修改以下配置（位于`main.py`的`CompleteInfoSpider`和`ShanghaiRankingSpider`类中）：
   ```python
   self.db_config = {
       'host': 'localhost',
       'user': 'root',           # 改为你的MySQL用户名
       'password': 'your_password', # 改为你的MySQL密码
       'database': 'kaoyan_data'
   }
   ```

2. **Edge驱动路径配置**
   在`main.py`中修改Edge驱动路径（第365行左右）：
   ```python
   driver_path = '../msedgedriver.exe'
   ```

3. **API密钥配置**
   创建`.streamlit/secrets.toml`文件并配置DeepSeek API密钥：
   ```toml
   DEEPSEEK_API_KEY = "your_deepseek_api_key_here"
   ```

## 📊 数据库设计

系统包含5个核心数据表：

### 1. **users** - 用户表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 用户ID，主键 |
| username | VARCHAR(50) | 用户名，唯一 |
| email | VARCHAR(100) | 邮箱，唯一 |
| password_hash | VARCHAR(255) | 密码哈希值 |
| created_at | TIMESTAMP | 创建时间 |
| last_login | TIMESTAMP | 最后登录时间 |
| is_active | BOOLEAN | 是否激活 |

### 2. **exam_subjects** - 考研专业信息表
存储从研招网爬取的招生专业信息，包含学校、专业、研究方向、考试科目等详细信息。

主要字段：
- `school_name`: 学校名称
- `major_name`: 专业名称
- `major_code`: 专业代码
- `department`: 开设院系
- `research_direction`: 研究方向
- `politics_subject`: 政治科目
- `foreign_language_subject`: 外语科目
- `business_subject1`: 业务课一
- `business_subject2`: 业务课二
- `enrollment_plan`: 拟招生人数
- `region`: 地区
- `degree_type`: 学位类型
- `search_type`: 搜索类型（地区/学校）

### 3. **shanghai_subject_rankings** - 软科排名表
存储软科2024-2025年学科排名数据，包含学科代码、学校名称、排名位置、分数等。

主要字段：
- `year`: 年份（2025）
- `subject_code`: 学科代码
- `subject_name`: 学科名称
- `ranking_position_2025`: 2025年排名
- `ranking_position_2024`: 2024年排名
- `school_name`: 学校名称
- `score_2025`: 2025年分数
- `score_2024`: 2024年分数
- `subject_category`: 学科类别
- `page_number`: 页码

### 4. **chat_history** - 聊天历史表
记录用户与AI的问答历史，支持历史记录查询。

### 5. **crawl_progress** - 爬虫进度表
记录爬虫执行状态，支持断点续爬。

## 🖥️ 使用说明

### 数据采集

#### 运行研招网爬虫
```bash
# 通过命令行交互界面运行
python main.py
```
程序将启动交互式爬虫界面，您可以选择：
1. **按地区搜索**：选择地区和院校特性（博士点、双一流、自划线），批量爬取学校专业信息
2. **按学校搜索**：输入具体学校名称，爬取指定学校信息
3. **数据管理**：删除已存在的数据或清空数据

#### 运行软科排名爬虫
通过交互界面选择：
1. **选择特定学科爬取**：选择单个或多个学科爬取
2. **爬取所有学科**：耗时较长，建议分批进行
3. **按学科类别爬取**：按学科大类批量爬取

### Web应用

#### 启动Web服务
```bash
streamlit run main.py
```

#### 主要功能界面

1. **登录/注册页面**
   - 新用户注册，需要验证邮箱格式和用户名格式
   - 已注册用户通过邮箱登录

2. **AI问答主界面**
   - **智能问答**：输入自然语言问题，获取基于数据库的准确回答
   - **示例问题**：提供常见问题示例，一键提问
   - **历史记录**：查看和清空聊天历史
   - **数据库预览**：展开查看AI回答背后的原始数据
   - **清空对话**：清空当前会话或永久删除历史记录

3. **数据查询页面**（四个选项卡）
   - **条件查询**：按学校、专业等条件筛选数据
   - **学校浏览**：按学校查看所有专业信息，分层浏览
   - **数据统计**：查看专业热度、地区分布等统计信息
   - **软科排名**：查询学科排名，支持前N名筛选、学科类别筛选

## 🔧 项目结构

```
kaoyan_assistant/
├── README.md                   # 项目说明文档
├── requirements.txt            # Python依赖包
├── main.py                     # 主程序文件（包含所有功能）
├── .streamlit/                 # Streamlit配置文件
│   └── secrets.toml           # API密钥配置文件
├── msedgedriver.exe           # Edge浏览器驱动（需自行下载）
├── crawler_*.log              # 爬虫日志文件（运行时生成）
├──AI对话Markdown/             # 导出的AI对话
├── 完整信息_考研专业信息-*.xlsx  # 导出的Excel数据文件
└── exports/                   # 导出目录
    └── shanghai_subject_rankings_*.xlsx  # 软科排名导出文件
```

## 🤖 AI使用说明

本系统使用了DeepSeek大语言模型API来生成智能回答：

### AI使用原则
1. **数据驱动**：所有回答均基于数据库真实信息，不添加未提及的信息
2. **准确优先**：优先保证信息的准确性，不进行主观评价
3. **结构清晰**：按学校、专业、研究方向、考试科目的顺序组织回答
4. **完整呈现**：列出数据库中所有相关信息，不遗漏
5. **客观解释**：如果数据库信息与常见认知有差异，基于数据库信息客观解释

### 提示词设计
系统使用精心设计的系统提示词来约束AI行为：
- 强调忠实于数据库信息
- 要求解释"不区分研究方向"等特殊情况
- 规定回答结构和完整性要求

## 📈 数据统计

系统内置数据统计功能，可以实时查看：
- **总记录数**：数据库中的专业信息总数
- **覆盖高校数**：数据涵盖的学校数量
- **专业数量**：不同的专业种类数
- **热门专业TOP 10**：最常出现的专业排名
- **地区分布**：各地区的专业分布情况（可视化图表）
- **学科排名统计**：各学科上榜学校数量、分数分布

## 🎯 核心查询示例

### 智能问答示例
1. **学校专业查询**："中国地质大学信息安全专业有哪些研究方向？"
2. **考试科目查询**："浙江大学计算机科学与技术专业的考试科目是什么？"
3. **学科排名查询**："软科数学专业排名前十的学校有哪些？"
4. **综合查询**："计算机科学与技术的软科排名情况如何？"

### 数据库查询示例
```sql
-- 查询计算机相关专业的考试科目
SELECT school_name, major_name, research_direction,
       politics_subject, foreign_language_subject,
       business_subject1, business_subject2
FROM exam_subjects
WHERE major_name LIKE '%计算机%'
ORDER BY school_name;

-- 查询数学学科排名前十
SELECT ranking_position_2025, school_name, score_2025
FROM shanghai_subject_rankings
WHERE subject_name = '数学'
ORDER BY ranking_position_2025
LIMIT 10;

-- 统计各地区计算机专业数量
SELECT region, COUNT(*) as count
FROM exam_subjects
WHERE major_name LIKE '%计算机%'
GROUP BY region
ORDER BY count DESC;
```

## ⚠️ 注意事项

1. **数据时效性**：爬虫数据基于爬取时网站状态，招生信息以官方最新发布为准
2. **API限制**：DeepSeek API有调用频率限制，请合理使用
3. **爬虫礼仪**：设置合理的请求间隔（3-8秒），避免对目标网站造成压力
4. **数据备份**：定期备份数据库，防止数据丢失
5. **隐私保护**：妥善保管API密钥和数据库密码，不要公开敏感信息
6. **浏览器驱动**：确保Edge驱动版本与浏览器版本匹配
7. **网络连接**：爬虫需要稳定的网络连接，建议在校园网环境下运行
8. **内存管理**：长时间运行爬虫可能占用较多内存，建议定期重启

---

**项目维护**：如有问题或建议，请提交Issue或Pull Request。

**数据来源声明**：
- 考研专业信息来源于中国研究生招生信息网（https://yz.chsi.com.cn/）
- 学科排名数据来源于软科排名（https://www.shanghairanking.cn/）
- AI服务基于DeepSeek大语言模型（https://www.deepseek.com/）

**免责声明**：本项目仅供学习和研究使用，请勿用于商业用途。数据准确性以官方发布为准。




