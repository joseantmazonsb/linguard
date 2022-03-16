namespace Linguard.Web.Services; 

public class WebService : IWebService {
    public bool IsSetupNeeded { get; set; } = true;
}