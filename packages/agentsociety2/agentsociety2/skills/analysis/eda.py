"""
为实验数据库表生成概览报告并纳入分析上下文

支持的 EDA 工具：
1. ydata-profiling: 全面的数据画像（统计、分布、缺失值、相关性）
2. sweetviz: 目标变量分析、相关性可视化
3. dtale: 交互式数据探索（可选）
4. missingno: 缺失值可视化
5. quick_stats: 快速统计摘要
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from agentsociety2.logger import get_logger

from .models import AnalysisConfig

_logger = get_logger()


def _get_all_tables_with_data(
    db_path: Path,
    max_rows_per_table: int = 10_000,
) -> List[Tuple[str, pd.DataFrame]]:
    """
    获取数据库中所有有数据的表及其数据。

    Returns:
        [(表名, DataFrame), ...] 列表
    """
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    tables_with_data = []

    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table}]")
                count = cursor.fetchone()[0]
                if count > 0:
                    df = pd.read_sql_query(
                        f"SELECT * FROM [{table}] LIMIT {max_rows_per_table}",
                        conn,
                    )
                    if not df.empty:
                        tables_with_data.append((table, df))
            except sqlite3.Error as e:
                _logger.debug(f"读取表 {table} 失败: {e}")
                continue
    finally:
        conn.close()

    return tables_with_data


def _load_first_table_df(
    db_path: Path,
    table_name: Optional[str] = None,
    max_rows: int = 10_000,
) -> Tuple[Optional[str], Optional[Any]]:
    """获取首个有数据的表并读成 DataFrame。返回 (表名, df) 或 (None, None)。"""
    if not db_path.exists():
        return None, None
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cur.fetchall()]
        if not tables:
            return None, None
        if table_name and table_name in tables:
            name = table_name
        else:
            name = None
            for t in tables:
                cur.execute(f"SELECT COUNT(*) FROM [{t}]")
                if cur.fetchone()[0] > 0:
                    name = t
                    break
            if name is None:
                return None, None
        df = pd.read_sql_query(f"SELECT * FROM [{name}] LIMIT {max_rows}", conn)
    finally:
        conn.close()
    return (name, df) if not df.empty else (None, None)


def generate_quick_stats(
    db_path: Path,
    table_name: Optional[str] = None,
    max_rows: int = 5_000,
    config: Optional[AnalysisConfig] = None,
) -> Optional[str]:
    """
    使用 pandas describe() 生成数值列统计摘要，返回 Markdown 文本。
    支持多表：如果未指定表名，生成所有有数据表的统计。
    """
    if table_name:
        name, df = _load_first_table_df(db_path, table_name, max_rows)
        if name is None or df is None:
            return None
        try:
            desc = df.describe(include="all")
            try:
                md = desc.to_markdown()
            except Exception:
                md = desc.to_string()
            return f"Table: {name}\n\n```\n{md}\n```"
        except Exception as e:
            _logger.debug("为 %s 生成快速统计摘要失败: %s", db_path, e)
            return None

    # 多表统计
    tables_data = _get_all_tables_with_data(db_path, max_rows)
    if not tables_data:
        return None

    lines = ["# Quick Statistics Summary\n"]
    for name, df in tables_data[:5]:  # 最多 5 个表
        try:
            desc = df.describe(include="all")
            try:
                md = desc.to_markdown()
            except Exception:
                md = desc.to_string()
            lines.append(f"## Table: {name} ({len(df)} rows sampled)\n")
            lines.append(f"```\n{md}\n```\n")
        except Exception as e:
            _logger.debug(f"表 {name} 统计失败: {e}")

    return "\n".join(lines) if len(lines) > 1 else None


def generate_eda_profile(
    db_path: Path,
    output_dir: Path,
    table_name: Optional[str] = None,
    max_rows: int = 10_000,
    config: Optional[AnalysisConfig] = None,
) -> Optional[Path]:
    """
    对 SQLite 中单表生成 EDA 概览 HTML。

    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        table_name: 指定表名；不传则取首个有数据的表
        max_rows: 最大行数，避免大表过慢

    Returns:
        生成的 HTML 路径，或 None（失败）
    """
    name, df = _load_first_table_df(db_path, table_name, max_rows)
    if name is None or df is None:
        return None

    from ydata_profiling import ProfileReport

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "eda_profile.html"
    try:
        profile = ProfileReport(df, title=f"EDA: {name}", minimal=True)
        profile.to_file(str(out_file))
        return out_file
    except Exception as e:
        _logger.debug("为 %s 生成EDA概览HTML失败: %s", db_path, e)
        return None


def generate_sweetviz_profile(
    db_path: Path,
    output_dir: Path,
    table_name: Optional[str] = None,
    max_rows: int = 10_000,
    config: Optional[AnalysisConfig] = None,
) -> Optional[Path]:
    """
    使用 Sweetviz 对 SQLite 单表生成 EDA HTML。
    与 ydata-profiling 互补：Sweetviz 侧重相关性、目标变量分析，界面更轻量。

    Args:
        db_path: 数据库路径
        output_dir: 输出目录
        table_name: 指定表名；不传则取首个有数据的表
        max_rows: 最大行数

    Returns:
        生成的 HTML 路径，或 None（失败）
    """
    name, df = _load_first_table_df(db_path, table_name, max_rows)
    if name is None or df is None:
        return None

    import sweetviz as sv

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "eda_sweetviz.html"
    try:
        report = sv.analyze(df)
        report.show_html(str(out_file), open_browser=False)
        return out_file if out_file.exists() else None
    except Exception as e:
        _logger.debug("为 %s 生成SweetvizEDA概览HTML失败: %s", db_path, e)
        return None


def generate_missingno_visualization(
    db_path: Path,
    output_dir: Path,
    table_name: Optional[str] = None,
    max_rows: int = 10_000,
    config: Optional[AnalysisConfig] = None,
) -> Optional[Path]:
    """
    使用 missingno 生成缺失值可视化。

    生成四种图：
    - matrix: 缺失值矩阵
    - bar: 缺失值条形图
    - heatmap: 缺失值相关性热力图
    - dendrogram: 缺失值树状图
    """
    name, df = _load_first_table_df(db_path, table_name, max_rows)
    if name is None or df is None:
        return None

    try:
        import missingno as msno
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        _logger.debug("missingno 未安装，跳过缺失值可视化")
        return None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 创建包含四个子图的图
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f"Missing Data Analysis: {name}", fontsize=14)

        # Matrix
        plt.sca(axes[0, 0])
        msno.matrix(df, ax=axes[0, 0])
        axes[0, 0].set_title("Missing Value Matrix")

        # Bar
        plt.sca(axes[0, 1])
        msno.bar(df, ax=axes[0, 1])
        axes[0, 1].set_title("Missing Value Counts")

        # Heatmap
        plt.sca(axes[1, 0])
        if df.isnull().sum().sum() > 0:
            msno.heatmap(df, ax=axes[1, 0])
        else:
            axes[1, 0].text(0.5, 0.5, "No Missing Values", ha="center", va="center")
        axes[1, 0].set_title("Missing Value Correlation")

        # Dendrogram
        plt.sca(axes[1, 1])
        if df.isnull().sum().sum() > 0:
            msno.dendrogram(df, ax=axes[1, 1])
        else:
            axes[1, 1].text(0.5, 0.5, "No Missing Values", ha="center", va="center")
        axes[1, 1].set_title("Missing Value Dendrogram")

        plt.tight_layout()
        out_file = output_dir / "eda_missingno.png"
        plt.savefig(out_file, dpi=150, bbox_inches="tight")
        plt.close()
        return out_file
    except Exception as e:
        _logger.debug("生成 missingno 可视化失败: %s", e)
        return None


def generate_multitable_summary(
    db_path: Path,
    output_dir: Path,
    max_rows_per_table: int = 5_000,
    config: Optional[AnalysisConfig] = None,
) -> Optional[Path]:
    """
    为所有表生成汇总报告（表格概览、行数统计、列类型统计）。
    """
    tables_data = _get_all_tables_with_data(db_path, max_rows_per_table)
    if not tables_data:
        return None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 创建汇总图
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        table_names = [t[0] for t in tables_data]
        row_counts = [len(t[1]) for t in tables_data]
        col_counts = [len(t[1].columns) for t in tables_data]

        # 行数条形图
        axes[0].barh(table_names, row_counts, color="steelblue")
        axes[0].set_xlabel("Row Count (sampled)")
        axes[0].set_title("Table Row Counts")
        axes[0].invert_yaxis()

        # 列数条形图
        axes[1].barh(table_names, col_counts, color="seagreen")
        axes[1].set_xlabel("Column Count")
        axes[1].set_title("Table Column Counts")
        axes[1].invert_yaxis()

        plt.tight_layout()
        out_file = output_dir / "eda_table_summary.png"
        plt.savefig(out_file, dpi=150, bbox_inches="tight")
        plt.close()
        return out_file
    except Exception as e:
        _logger.debug("生成多表汇总失败: %s", e)
        return None


def generate_full_eda_report(
    db_path: Path,
    output_dir: Path,
    config: Optional[AnalysisConfig] = None,
) -> Dict[str, Optional[Path]]:
    """
    生成完整的 EDA 报告套件。

    Returns:
        {
            "eda_profile": Path or None,
            "eda_sweetviz": Path or None,
            "eda_missingno": Path or None,
            "eda_table_summary": Path or None,
        }
    """
    results: Dict[str, Optional[Path]] = {
        "eda_profile": None,
        "eda_sweetviz": None,
        "eda_missingno": None,
        "eda_table_summary": None,
    }

    if not db_path.exists():
        return results

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成 ydata-profiling 报告
    results["eda_profile"] = generate_eda_profile(db_path, output_dir, config=config)

    # 生成 Sweetviz 报告
    results["eda_sweetviz"] = generate_sweetviz_profile(db_path, output_dir, config=config)

    # 生成缺失值可视化
    results["eda_missingno"] = generate_missingno_visualization(db_path, output_dir, config=config)

    # 生成多表汇总
    results["eda_table_summary"] = generate_multitable_summary(db_path, output_dir, config=config)

    return results
