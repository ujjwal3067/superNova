// author ujjwal
#include <iostream>
#include <list>
using namespace std;
int main()
{
    list<char> A, B;
    char C;
    while (cin.get(C) && C != '\n')
    {
        A.push_back(C);
    }
    while (cin.get(C) && C != '\n')
    {
        B.push_back(C);
    }
    while (!A.empty() && !B.empty() && A.front() == B.front())
    {
        A.pop_front();
        B.pop_front();
    }
    while (!A.empty() && !B.empty() && A.back() == B.back())
    {
        A.pop_back();
        B.pop_back();
    }
    cout << B.size() << endl;
}