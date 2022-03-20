using Linguard.Core.Models;
using Linguard.Web.Configuration;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Linguard.Web.Pages; 

public class HostModel : PageModel {
    private readonly IConfigurationManager _configurationManager;

    public HostModel(IConfigurationManager configurationManager) {
        _configurationManager = configurationManager;
    }

    private IWebConfiguration Configuration => _configurationManager.Configuration.GetModule<IWebConfiguration>()!;
    public static string Stylesheet => $"_content/Radzen.Blazor/css/{Style.Default}.css";
    
}