namespace Linguard.Web.Configuration; 

public interface IConfiguration : Core.Configuration.IConfiguration {
    public IWebOptions Web { get; set; }
}