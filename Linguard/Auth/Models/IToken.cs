namespace Auth.Models; 

public interface IToken {
    public string Value { get; }
    public DateTime ValidUntil { get; }
}