using System;

namespace OperatorPackage.Core
{
    public interface IOperator<TInput, TOutput>
    {
        TOutput Execute(TInput input);
    }
}