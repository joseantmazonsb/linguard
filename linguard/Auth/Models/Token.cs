namespace Auth.Models; 

public class Token : IToken {
    public Token(string value, DateTime validUntil) {
        Value = value;
        ValidUntil = validUntil;
    }

    public string Value { get; }
    public DateTime ValidUntil { get; }
}