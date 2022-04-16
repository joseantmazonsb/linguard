using Linguard.Core.Models;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace Linguard.Web.Pages; 

public class HostModel : PageModel {
    public static string Stylesheet => $"_content/Radzen.Blazor/css/{Style.Default}.css";
    
}