namespace Linguard.Core.Models; 

public enum Style {
    Default,
    Standard,
    Humanistic,
    Software,
    Dark
}

public static class StyleUtils {

    private const string Parent = "_content/Radzen.Blazor/css/";
    private const string Extension = ".css";
    
    public static string GetStylesheet(Style style) 
        => $"{Parent}{style.ToString().ToLower()}{Extension}";
}

