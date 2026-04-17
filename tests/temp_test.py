from ndlmpanel_agent.tools.ops.filesystem.filesystem_tools import (
    grepFileOrDirectory,
)


def test_grep_init_files():
    """测试递归查找所有 __init__.py 文件"""
    print("\n" + "="*70)
    print("测试 1: 递归查找所有 __init__.py 文件")
    print("="*70)
    try:
        result = grepFileOrDirectory(
            targetPath="./src",
            regExpr="__init__\\.py",
            recursive=True,
            searchFileNames=True,
        )
        
        print("✓ 搜索成功!")
        print(f"  模式: {result.pattern}")
        print(f"  目标: {result.targetPath}")
        print(f"  匹配数: {result.totalMatches}")
        print("\n  匹配结果:")
        
        for i, match in enumerate(result.matches, 1):
            print(f"    {i}. {match.fileInfo.absolutePath}")
            print(f"       所有者: {match.fileInfo.owner}, 大小: {match.fileInfo.sizeBytes} bytes")
            
    except Exception as e:
        print(f"✗ 异常: {type(e).__name__}: {e}")



def test_grep_all_py_files():
    """测试查找所有 .py 文件"""
    print("\n" + "="*70)
    print("测试 2: 递归查找所有 .py 文件")
    print("="*70)
    try:
        result = grepFileOrDirectory(
            targetPath="./src",
            regExpr="\\.py",
            recursive=True,
            searchFileNames=True,
        )
        
        print("✓ 搜索成功!")
        print(f"  模式: {result.pattern}")
        print(f"  目标: {result.targetPath}")
        print(f"  匹配数: {result.totalMatches}")
        
        # 统计不同类型的文件
        file_names = {}
        for match in result.matches:
            file_name = match.fileInfo.fileName
            file_names[file_name] = file_names.get(file_name, 0) + 1
        
        print("\n  前10个匹配结果:")
        for i, match in enumerate(result.matches[:10], 1):
            print(f"    {i}. {match.fileInfo.absolutePath}")
            
        if len(result.matches) > 10:
            print(f"    ... 还有 {len(result.matches) - 10} 个结果")
            
    except Exception as e:
        print(f"✗ 异常: {type(e).__name__}: {e}")



def test_grep_case_insensitive():
    """测试不区分大小写的搜索文件内容"""
    print("\n" + "="*70)
    print("测试 3: 不区分大小写查找文件内容中的 'def'")
    print("="*70)
    try:
        result = grepFileOrDirectory(
            targetPath="./src/ndlmpanel_agent/tools/ops/filesystem",
            regExpr="def",
            recursive=True,
            ignoreCase=True,
            searchFileNames=False,  # 搜索文件内容
        )
        
        print("✓ 搜索成功!")
        print(f"  模式: {result.pattern}")
        print(f"  目标: {result.targetPath}")
        print(f"  匹配数: {result.totalMatches}")
        print("\n  前15个匹配结果:")
        
        for i, match in enumerate(result.matches[:15], 1):
            # 显示包含 'def' 的行
            print(f"    {i}. [{match.fileInfo.absolutePath}:{match.lineNumber}]")
            print(f"       权限: {match.fileInfo.permissions}")
            print(f"       内容: {match.lineContent[:70]}")
            
        if len(result.matches) > 15:
            print(f"    ... 还有 {len(result.matches) - 15} 个结果")
            
    except Exception as e:
        print(f"✗ 异常: {type(e).__name__}: {e}")



def main():
    test_grep_init_files()
    test_grep_all_py_files()
    test_grep_case_insensitive()


if __name__ == "__main__":
    main()
