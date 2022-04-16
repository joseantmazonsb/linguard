namespace Linguard.Core.Configuration; 

public interface IAuthenticationOptions : IOptionsModule {
    /// <summary>
    /// Indicate the data source used to validate and authenticate users.  
    /// </summary>
    /// <remarks>It may be a path to a file or a connection string, for instance.</remarks>
    string DataSource { get; set; }
}