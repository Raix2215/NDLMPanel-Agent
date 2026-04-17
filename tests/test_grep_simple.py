#!/usr/bin/env python3
"""简单的grep功能测试"""

from ndlmpanel_agent.tools.ops.filesystem.filesystem_tools import grepFileOrDirectory


def main():
    print("\n" + "="*70)
    print("测试 1: 递归查找所有 __init__.py 文件")
    print("="*70)
    
    result = grepFileOrDirectory(
        targetPath="./src",
        regExpr="__init__\\.py",
        recursive=True,
        searchFileNames=True,
    )
    
    print(f"✓ 搜索成功!")
    print(f"  模式: {result.pattern}")
    print(f"  匹配数: {result.totalMatches}")
    print(f"  匹配结果:")
    
    for i, match in enumerate(result.matches, 1):
        print(f"    {i}. {match.fileInfo.absolutePath}")
        print(f"       文件类型: {match.fileInfo.fileType}, 大小: {match.fileInfo.sizeBytes} bytes")
    
    print("\n" + "="*70)
    print("测试 2: 递归查找所有 .py 文件")
    print("="*70)
    
    result = grepFileOrDirectory(
        targetPath="./src",
        regExpr="\\.py",
        recursive=True,
        searchFileNames=True,
    )
    
    print(f"✓ 搜索成功!")
    print(f"  模式: {result.pattern}")
    print(f"  匹配数: {result.totalMatches}")
    print(f"  前10个匹配结果:")
    
    for i, match in enumerate(result.matches[:10], 1):
        print(f"    {i}. {match.fileInfo.absolutePath}")
    
    if len(result.matches) > 10:
        print(f"    ... 还有 {len(result.matches) - 10} 个结果")
    
    print("\n" + "="*70)
    print("测试 3: 搜索文件内容中的 'def '")
    print("="*70)
    
    result = grepFileOrDirectory(
        targetPath="./src/ndlmpanel_agent/tools/ops/filesystem",
        regExpr="def ",
        recursive=True,
        ignoreCase=False,
        searchFileNames=False,
    )
    
    print(f"✓ 搜索成功!")
    print(f"  模式: {result.pattern}")
    print(f"  匹配数: {result.totalMatches}")
    print(f"  前10个匹配结果:")
    
    for i, match in enumerate(result.matches[:10], 1):
        print(f"    {i}. [{match.fileInfo.absolutePath}:{match.lineNumber}]")
        print(f"       {match.lineContent.strip()[:70]}")


if __name__ == "__main__":
    main()

