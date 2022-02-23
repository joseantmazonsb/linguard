namespace Linguard.Core.Models; 

public class User {
    public string Nickname { get; set; }
    public string Email { get; set; }
    public string Password { get; set; }
    public DateTime LastLogin { get; set; }
}