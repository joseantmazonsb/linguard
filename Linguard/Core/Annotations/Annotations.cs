namespace Linguard.Core.Annotations; 

/// <summary>
/// Indicates that a property MAY have value. 
/// </summary>
[AttributeUsage(AttributeTargets.Property)]
public class OptionalAttribute : Attribute {
}

/// <summary>
/// Indicates that a property MUST have value.
/// </summary>
[AttributeUsage(AttributeTargets.Property)]
public class MandatoryAttribute : Attribute {
}