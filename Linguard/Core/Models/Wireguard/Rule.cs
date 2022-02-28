namespace Linguard.Core.Models.Wireguard; 

public class Rule {
    public string Command { get; set; }
    
    public static implicit operator Rule(string command)
    {
        return new Rule {
            Command = command
        };
    }
}