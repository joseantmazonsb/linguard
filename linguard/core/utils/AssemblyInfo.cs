using System.Diagnostics;
using System.Reflection;

namespace Linguard.Core.Utils; 

public static class AssemblyInfo {

    public static FileVersionInfo Version => FileVersionInfo.GetVersionInfo(Assembly.GetCallingAssembly().Location);
    
    public static string Product => Assembly.GetCallingAssembly()
        .GetCustomAttribute<AssemblyProductAttribute>()!
        .Product;
    
    public static string Title => Assembly.GetCallingAssembly()
        .GetCustomAttribute<AssemblyTitleAttribute>()!
        .Title;
}