namespace Linguard.Core.Exceptions; 

public abstract class ExtendedException : Exception {
    protected ExtendedException() { }
    protected ExtendedException(string message) : base(message) { }
    protected ExtendedException(string message, Exception innerException) 
        : base(message, innerException) { }

    public abstract IEnumerable<string> Fixes { get; }
}