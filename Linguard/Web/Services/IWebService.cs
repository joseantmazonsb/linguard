namespace Linguard.Web.Services; 

public interface IWebService {
    /// <summary>
    /// Flag used to tell whether the initial setup has been completed.
    /// </summary>
    bool IsSetupNeeded { get; set; }
}