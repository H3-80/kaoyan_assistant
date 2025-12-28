问题出在你的主函数逻辑上。你需要在代码入口处明确区分 Streamlit 应用和命令行爬虫工具。以下是修复方案：

## 方案一：完全分离（推荐）

**步骤1：创建两个独立的主文件**

```
import streamlit as st


if __name__ == "__main__":
    main()
```

```



if __name__ == "__main__":
    interactive_crawler_ui()
```

## 方案二：修改现有代码（在当前文件基础上修复）

修改你的 `main.py` 文件，替换最后的代码部分：

```

def is_running_in_streamlit():
    """检查是否在Streamlit环境中运行"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except:
        
        return False


def streamlit_main():
    """Streamlit应用的入口函数"""
    
    if 'MYSQL_AVAILABLE' not in globals():
        global MYSQL_AVAILABLE
        MYSQL_AVAILABLE = True

    
    if 'db_initialized' not in st.session_state:
        if init_database():
            st.session_state.db_initialized = True
        else:
            st.error("数据库初始化失败，请检查数据库连接")
            return

    
    if 'page' not in st.session_state:
        st.session_state.page = "login"

    
    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "register":
        register_page()
    elif st.session_state.page == "main":
        if 'user' in st.session_state:
            main_page()
        else:
            st.session_state.page = "login"
            st.rerun()
    elif st.session_state.page == "data_query":
        if 'user' in st.session_state:
            data_query_page()
        else:
            st.session_state.page = "login"
            st.rerun()


def command_line_main():
    """命令行爬虫工具的入口函数"""
    interactive_crawler_ui()




if __name__ == "__main__":
    
    if is_running_in_streamlit():
        
        streamlit_main()
    else:
        
        command_line_main()
```

## 方案三：更简单的环境检测方法

如果你觉得上面的方法太复杂，可以使用这个更简单的版本：

```

if __name__ == "__main__":
    
    import sys
    
    if len(sys.argv) > 0 and "streamlit" in sys.argv[0]:
        
        print("检测到Streamlit环境，启动Web界面...")
        
        
        if 'MYSQL_AVAILABLE' not in globals():
            global MYSQL_AVAILABLE
            MYSQL_AVAILABLE = True

        
        if 'db_initialized' not in st.session_state:
            if init_database():
                st.session_state.db_initialized = True
            else:
                st.error("数据库初始化失败，请检查数据库连接")
                st.stop()

        
        if 'page' not in st.session_state:
            st.session_state.page = "login"

        
        if st.session_state.page == "login":
            login_page()
        elif st.session_state.page == "register":
            register_page()
        elif st.session_state.page == "main":
            if 'user' in st.session_state:
                main_page()
            else:
                st.session_state.page = "login"
                st.rerun()
        elif st.session_state.page == "data_query":
            if 'user' in st.session_state:
                data_query_page()
            else:
                st.session_state.page = "login"
                st.rerun()
    else:
        
        print("检测到命令行环境，启动交互式爬虫界面...")
        interactive_crawler_ui()
```

## 使用说明

1.  **启动Streamlit Web界面**：
    
2.  **启动命令行爬虫工具**：
    

## 推荐的文件结构

```
kaoyan_assistant/
├── main_streamlit.py    # Streamlit Web应用
├── main_crawler.py      # 命令行爬虫工具
├── modules/
│   ├── spider.py        # 爬虫类
│   ├── database.py      # 数据库操作
│   └── utils.py         # 工具函数
├── data/                # 数据文件
├── logs/                # 日志文件
└── requirements.txt     # 依赖文件
```

这样分离后，两个功能互不干扰，代码也更清晰易维护。建议采用**方案一**的完全分离方式，这是最规范和可维护的方案。