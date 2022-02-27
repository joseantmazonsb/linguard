namespace Linguard.Core.Configuration; 

public class Configuration : IConfiguration {
    public IWireguardConfiguration Wireguard { get; set; } = new WireguardConfiguration();
    public ILoggingConfiguration Logging { get; set; } = new LoggingConfiguration();
    public IWebConfiguration Web { get; set; } = new WebConfiguration();
    public ITrafficConfiguration Traffic { get; set; } = new TrafficConfiguration();
    
    public object Clone() {
        var clone = (IConfiguration) MemberwiseClone();
        var cloneableProperties = GetType().GetProperties()
            .Where(p => p.PropertyType.GetInterfaces().Contains(typeof(ICloneable)));
        foreach (var property in cloneableProperties) {
            var propertyValue = property.GetValue(this);
            var propertyClone = propertyValue?.GetType().GetMethod(nameof(Clone))
                !.Invoke(propertyValue, Array.Empty<object>());
            property.SetValue(clone, propertyClone);
        }
        return clone;
    }
}