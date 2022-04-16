using Linguard.Core.Configuration;

namespace Linguard.Web.Configuration; 

/// <summary>
/// Web related settings.
/// </summary>
public interface IWebOptions : IOptionsModule {
    public int LoginAttempts { get; set; }
    public TimeSpan LoginBanTime { get; set; }
}