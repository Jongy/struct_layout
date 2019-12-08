#include <stdbool.h>

struct other_struct {
    int some_field;
};

union my_union {
    int x;
    char y;
};

enum e1 {
    x = 5,
};

struct outer {
    struct {
        int a;
        int b;
    } inner;

    union {
        int c;
        int d;
    };

    struct {
        int z;
    };

    int ar[];
};

struct test_struct {
    int first_field;
    char second_field;
    unsigned long *third_field;
    float last_field;

    int my_array[17];

    void **p;

    struct other_struct z;

    union my_union u;

    enum e1 e1;

    enum {
        y = 1,
    } e2;

    int twodim[3][2];

    char bitfield1: 1;
    char bitfield2: 5;
    int between_bitfields;
    int bitfield3: 2;

    bool bb;

    struct outer o;

    __builtin_va_list va_list;

    int arr[0];
};
