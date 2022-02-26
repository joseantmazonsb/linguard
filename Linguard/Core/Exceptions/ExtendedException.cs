namespace Linguard.Core.Exceptions; 

public abstract class ExtendedException : Exception {
    protected ExtendedException(IEnumerable<string> fixes) {
        Fixes = fixes;
    }
    protected ExtendedException(string message, IEnumerable<string> fixes) : base(message) {
        Fixes = fixes;
    }
    protected ExtendedException(string message, Exception innerException, IEnumerable<string> fixes) 
        : base(message, innerException) {
        Fixes = fixes;
    }

    public IEnumerable<string> Fixes { get; }
}