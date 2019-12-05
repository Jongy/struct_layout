struct other_struct {
    int some_field;
};

union my_union {
    int x;
    char y;
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

    int twodim[3][2];
};
