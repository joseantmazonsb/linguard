﻿using Linguard.Log;

namespace Linguard.Core.Configuration; 

public class LoggingConfiguration : ILoggingConfiguration{
    public LogLevel Level { get; set; } = LogLevel.Info;
    public bool Overwrite { get; set; }
    
    public object Clone() {
        return MemberwiseClone();
    }
}